"""
uiuc_parser.py

Downloads and parses UIUC Airfoil Coordinates Database .dat files.

Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database
    https://m-selig.ae.illinois.edu/ads/coord_database.html

Supports both Selig and Lednicer .dat formats (auto-detected).
All coordinates are normalised to unit chord (x ∈ [0, 1]).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen, urlretrieve

import numpy as np

logger = logging.getLogger(__name__)

_UIUC_BASE_URL = "https://m-selig.ae.illinois.edu/ads/coord"
_UIUC_INDEX_URL = "https://m-selig.ae.illinois.edu/ads/coord_database.html"
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "airfoils"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AirfoilGeometry:
    """Parsed airfoil geometry from a UIUC .dat coordinate file.

    Attributes:
        name: Airfoil name as read from the .dat file header.
        coordinates: (N, 2) array of (x, y) coordinates, unit chord.
        thickness_ratio: Maximum thickness-to-chord ratio (e.g. 0.12).

    Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database.
    """
    name: str
    coordinates: np.ndarray  # shape (N, 2)
    thickness_ratio: float


# ---------------------------------------------------------------------------
# Format detection helpers
# ---------------------------------------------------------------------------

def _try_parse_floats(line: str) -> list[float] | None:
    """Try to parse a whitespace-delimited line as a list of floats."""
    parts = line.strip().split()
    if not parts:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def _detect_format(lines: list[str]) -> str:
    """Detect whether a .dat file is Selig or Lednicer format.

    Selig format:
        Line 0: airfoil name
        Line 1+: x y coordinate pairs (continuous)

    Lednicer format:
        Line 0: airfoil name
        Line 1: two numbers (upper_count  lower_count)
        Line 2: blank
        Lines 3+: coordinates in two blocks

    Returns:
        'selig' or 'lednicer'
    """
    # Skip blank lines after the name to find the first data line
    for i in range(1, min(len(lines), 5)):
        stripped = lines[i].strip()
        if not stripped:
            continue
        vals = _try_parse_floats(stripped)
        if vals is None:
            continue
        # Lednicer: the first numeric line after the name has two values
        # that are both > 1 (point counts, e.g. "33.  33." or "33 33")
        if len(vals) == 2 and vals[0] > 1.5 and vals[1] > 1.5:
            return "lednicer"
        # If the first numeric line has values in [0, 1] range it's Selig
        if len(vals) == 2 and 0.0 <= vals[0] <= 1.0001:
            return "selig"
        break

    # Default to Selig
    return "selig"


# ---------------------------------------------------------------------------
# Parsing implementations
# ---------------------------------------------------------------------------

def _parse_selig(lines: list[str]) -> tuple[str, np.ndarray]:
    """Parse a Selig-format .dat file.

    Selig format: header name, then continuous x y pairs
    (upper surface TE → LE → lower surface TE).

    Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database.
    """
    name = lines[0].strip()
    coords: list[list[float]] = []

    for line in lines[1:]:
        vals = _try_parse_floats(line)
        if vals is not None and len(vals) >= 2:
            coords.append([vals[0], vals[1]])

    if len(coords) < 3:
        raise ValueError(f"Too few coordinate points ({len(coords)}) in Selig file")

    return name, np.array(coords, dtype=np.float64)


def _parse_lednicer(lines: list[str]) -> tuple[str, np.ndarray]:
    """Parse a Lednicer-format .dat file.

    Lednicer format: header name, then (upper_count lower_count),
    blank separator, upper surface block, blank separator, lower surface block.

    Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database.
    """
    name = lines[0].strip()

    # Find the count line
    count_vals = None
    count_idx = 0
    for i in range(1, min(len(lines), 5)):
        count_vals = _try_parse_floats(lines[i])
        if count_vals is not None and len(count_vals) >= 2:
            count_idx = i
            break

    if count_vals is None:
        raise ValueError("Could not find point counts in Lednicer file")

    n_upper = int(round(count_vals[0]))
    n_lower = int(round(count_vals[1]))

    # Parse all remaining coordinate lines, splitting on blank lines
    blocks: list[list[list[float]]] = []
    current_block: list[list[float]] = []

    for line in lines[count_idx + 1:]:
        vals = _try_parse_floats(line)
        if vals is not None and len(vals) >= 2:
            current_block.append([vals[0], vals[1]])
        else:
            if current_block:
                blocks.append(current_block)
                current_block = []
    if current_block:
        blocks.append(current_block)

    if len(blocks) < 2:
        raise ValueError(
            f"Expected 2 coordinate blocks in Lednicer file, found {len(blocks)}"
        )

    upper = np.array(blocks[0], dtype=np.float64)
    lower = np.array(blocks[1], dtype=np.float64)

    # Combine: upper surface (TE→LE) then lower surface (LE→TE)
    # Upper is typically ordered LE→TE in Lednicer, reverse it to get TE→LE
    if len(upper) > 1 and upper[0, 0] < upper[-1, 0]:
        upper = upper[::-1]

    # Concatenate (skip duplicate LE point if present)
    if np.allclose(upper[-1], lower[0], atol=1e-6):
        coords = np.vstack([upper, lower[1:]])
    else:
        coords = np.vstack([upper, lower])

    return name, coords


# ---------------------------------------------------------------------------
# Thickness computation
# ---------------------------------------------------------------------------

def _compute_thickness_ratio(coords: np.ndarray) -> float:
    """Compute max thickness-to-chord ratio from airfoil coordinates.

    Splits coordinates into upper and lower surfaces, interpolates
    both onto common x stations, and finds max(y_upper − y_lower).

    Source: Standard geometric definition of airfoil thickness ratio,
        Abbott & Von Doenhoff, 'Theory of Wing Sections', Chapter 6.

    Args:
        coords: (N, 2) array of airfoil coordinates, unit chord.

    Returns:
        Maximum thickness / chord (dimensionless).
    """
    x = coords[:, 0]
    y = coords[:, 1]

    # Find the leading edge (minimum x)
    le_idx = np.argmin(x)

    # Split into upper (TE→LE) and lower (LE→TE) surfaces
    upper_x = x[:le_idx + 1]
    upper_y = y[:le_idx + 1]
    lower_x = x[le_idx:]
    lower_y = y[le_idx:]

    # Ensure upper surface x is increasing for interpolation
    if len(upper_x) > 1 and upper_x[0] > upper_x[-1]:
        upper_x = upper_x[::-1]
        upper_y = upper_y[::-1]

    # Ensure lower surface x is increasing
    if len(lower_x) > 1 and lower_x[0] > lower_x[-1]:
        lower_x = lower_x[::-1]
        lower_y = lower_y[::-1]

    # Common x stations for interpolation
    x_min = max(np.min(upper_x), np.min(lower_x))
    x_max = min(np.max(upper_x), np.max(lower_x))

    if x_max <= x_min:
        logger.warning("Cannot compute thickness: no overlapping x range")
        return 0.0

    x_common = np.linspace(x_min, x_max, 200)
    y_upper_interp = np.interp(x_common, upper_x, upper_y)
    y_lower_interp = np.interp(x_common, lower_x, lower_y)

    thickness = y_upper_interp - y_lower_interp
    return float(np.max(thickness))


# ---------------------------------------------------------------------------
# XFOIL-safe file I/O
# ---------------------------------------------------------------------------

def _write_selig_dat(path: Path, name: str, coords: np.ndarray) -> None:
    """Write airfoil coordinates in clean Selig format.

    Produces a .dat file that XFOIL can LOAD without errors:
    line 1 is the airfoil name, followed by x y coordinate pairs.
    No point-count lines, no blank separators, no format artifacts.

    Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database.

    Args:
        path: Output file path.
        name: Airfoil name (written as the first line).
        coords: (N, 2) array of (x, y) coordinates.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{name}\n")
        for x, y in coords:
            f.write(f" {x: .7f} {y: .7f}\n")


def _is_clean_selig(path: Path) -> bool:
    """Check whether a .dat file is already in clean Selig format.

    A clean Selig file has a name line, then only lines parseable as
    two floats in the [0, 1] x-range.  Any point-count line (values > 1)
    or blank separator between coordinate blocks means it needs re-writing.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False

    if len(lines) < 3:
        return False

    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        vals = _try_parse_floats(stripped)
        if vals is None:
            continue
        # A point-count line (e.g. "66. 66.") has values > 1.5
        if len(vals) >= 2 and (vals[0] > 1.5 or vals[1] > 1.5):
            return False
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_dat_file(path: Path) -> AirfoilGeometry:
    """Parse a UIUC-format .dat airfoil coordinate file.

    Auto-detects Selig vs Lednicer format. Computes the maximum
    thickness-to-chord ratio from the coordinate geometry.

    Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database.

    Args:
        path: Path to the .dat file.

    Returns:
        AirfoilGeometry with name, coordinates, and thickness_ratio.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If the file cannot be parsed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Airfoil .dat file not found: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) < 3:
        raise ValueError(f"File too short to be a valid .dat file: {path}")

    fmt = _detect_format(lines)
    logger.info("Detected %s format for %s", fmt, path.name)

    if fmt == "lednicer":
        name, coords = _parse_lednicer(lines)
    else:
        name, coords = _parse_selig(lines)

    thickness = _compute_thickness_ratio(coords)
    logger.info("Parsed %s: %d points, thickness=%.4f", name, len(coords), thickness)

    return AirfoilGeometry(
        name=name,
        coordinates=coords,
        thickness_ratio=thickness,
    )


def fetch_airfoil(
    airfoil_id: str,
    cache_dir: Path | None = None,
) -> AirfoilGeometry:
    """Download and parse an airfoil from the UIUC database.

    Downloads the .dat coordinate file from the UIUC Applied Aerodynamics
    Group Airfoil Coordinates Database, parses it (handling both Selig
    and Lednicer formats), and caches a **clean Selig-format** copy
    that XFOIL can LOAD directly without errors.

    Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database.
        URL: https://m-selig.ae.illinois.edu/ads/coord_database.html

    Args:
        airfoil_id: Airfoil identifier (e.g. 'n0012', 'clarky').
            Must match the filename on the UIUC server (without .dat).
        cache_dir: Local directory for caching downloaded files.
            Defaults to ``<project_root>/data/airfoils/``.

    Returns:
        AirfoilGeometry with name, coordinates, and thickness_ratio.

    Raises:
        urllib.error.URLError: If the download fails.
        ValueError: If the file cannot be parsed.
    """
    if cache_dir is None:
        cache_dir = _DEFAULT_CACHE_DIR

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    dat_path = cache_dir / f"{airfoil_id}.dat"

    if dat_path.exists() and _is_clean_selig(dat_path):
        logger.info("Using cached (clean Selig) %s", dat_path)
        return parse_dat_file(dat_path)

    # Download raw file (may be Lednicer or Selig with artifacts)
    raw_path = cache_dir / f"{airfoil_id}.dat.raw"
    if not dat_path.exists():
        url = f"{_UIUC_BASE_URL}/{airfoil_id}.dat"
        logger.info("Downloading %s → %s", url, raw_path)
        urlretrieve(url, raw_path)
    else:
        # Cached file exists but is not clean Selig — re-process it
        logger.info("Re-processing cached %s (not clean Selig)", dat_path)
        dat_path.rename(raw_path)

    # Parse the raw file (handles both Selig and Lednicer)
    geom = parse_dat_file(raw_path)

    # Re-write as clean Selig format for XFOIL compatibility
    _write_selig_dat(dat_path, geom.name, geom.coordinates)
    logger.info("Wrote clean Selig file: %s (%d points)",
                dat_path, len(geom.coordinates))

    # Remove the raw download
    try:
        raw_path.unlink()
    except OSError:
        pass

    return geom


class _DatLinkParser(HTMLParser):
    """Extract .dat file links from the UIUC index page."""

    def __init__(self) -> None:
        super().__init__()
        self.airfoil_ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for attr_name, attr_val in attrs:
            if attr_name == "href" and attr_val and attr_val.endswith(".dat"):
                # Extract filename without extension
                filename = attr_val.rsplit("/", 1)[-1]
                airfoil_id = filename.removesuffix(".dat")
                self.airfoil_ids.append(airfoil_id)


def list_available_airfoils() -> list[str]:
    """Scrape the UIUC index page and return available airfoil IDs.

    Data source: UIUC Applied Aerodynamics Group, Airfoil Coordinates Database.
        URL: https://m-selig.ae.illinois.edu/ads/coord_database.html

    Returns:
        Sorted list of airfoil ID strings (e.g. ['ag03', 'ag04', ..., 'naca0012', ...]).
    """
    logger.info("Fetching airfoil index from %s", _UIUC_INDEX_URL)
    with urlopen(_UIUC_INDEX_URL) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = _DatLinkParser()
    parser.feed(html)

    unique = sorted(set(parser.airfoil_ids))
    logger.info("Found %d airfoils in UIUC database", len(unique))
    return unique

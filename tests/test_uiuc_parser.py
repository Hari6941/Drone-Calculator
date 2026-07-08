"""
test_uiuc_parser.py

Tests for the UIUC airfoil .dat parser.

Validation cases sourced from:
    - NACA 0012: Abbott & Von Doenhoff, "Theory of Wing Sections" — 12% thick symmetric
    - Clark Y: Standard specification — 11.7% thick, cambered
    - UIUC Applied Aerodynamics Group, Airfoil Coordinates Database

Run with:  pytest tests/test_uiuc_parser.py -v
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from airfoil_engine.uiuc_parser import (
    AirfoilGeometry,
    fetch_airfoil,
    parse_dat_file,
    validate_dat_file,
)


# ---------------------------------------------------------------------------
# Validation case 1: NACA 0012 (symmetric, 12% thick)
# Source: Abbott & Von Doenhoff, "Theory of Wing Sections"
# ---------------------------------------------------------------------------

@pytest.mark.network
def test_parse_naca0012():
    """NACA 0012: thickness ≈ 12%, symmetric about chord line."""
    geom = fetch_airfoil("n0012")

    # Name should contain '0012' or 'NACA'
    assert "0012" in geom.name.upper() or "NACA" in geom.name.upper() or "N0012" in geom.name.upper()

    # Thickness ratio: 12% ± 1%
    assert geom.thickness_ratio == pytest.approx(0.12, abs=0.01), (
        f"NACA 0012 thickness_ratio={geom.thickness_ratio:.4f}, expected ~0.12"
    )

    # Coordinates shape: (N, 2), N > 50
    assert geom.coordinates.ndim == 2
    assert geom.coordinates.shape[1] == 2
    assert geom.coordinates.shape[0] > 50, (
        f"Too few points: {geom.coordinates.shape[0]}"
    )

    # x values in [0, 1] (unit chord)
    x = geom.coordinates[:, 0]
    assert np.all(x >= -0.001), f"x min = {x.min()}"
    assert np.all(x <= 1.001), f"x max = {x.max()}"

    # Symmetric: mean y ≈ 0
    y = geom.coordinates[:, 1]
    assert np.mean(y) == pytest.approx(0.0, abs=0.01), (
        f"NACA 0012 mean(y)={np.mean(y):.4f}, expected ~0 (symmetric)"
    )


# ---------------------------------------------------------------------------
# Validation case 2: Clark Y (cambered, 11.7% thick)
# Source: Standard Clark Y specification
# ---------------------------------------------------------------------------

@pytest.mark.network
def test_parse_clarky():
    """Clark Y: thickness ≈ 11.7%, positively cambered."""
    geom = fetch_airfoil("clarky")

    # Thickness ratio: 11.7% ± 1.5%
    assert geom.thickness_ratio == pytest.approx(0.117, abs=0.015), (
        f"Clark Y thickness_ratio={geom.thickness_ratio:.4f}, expected ~0.117"
    )

    # Coordinates shape
    assert geom.coordinates.ndim == 2
    assert geom.coordinates.shape[1] == 2
    assert geom.coordinates.shape[0] > 50

    # Cambered: mean y should be positive
    y = geom.coordinates[:, 1]
    assert np.mean(y) > 0.01, (
        f"Clark Y mean(y)={np.mean(y):.4f}, expected > 0.01 (cambered)"
    )


# ---------------------------------------------------------------------------
# Unit test: parse a synthetic Selig-format .dat file
# ---------------------------------------------------------------------------

def test_parse_dat_file_directly(tmp_path: Path):
    """Parse a minimal synthetic Selig-format .dat file."""
    # Create a simple symmetric "airfoil" with 5 points:
    # TE(upper) → LE → TE(lower)
    dat_content = (
        "Test Airfoil\n"
        "  1.0000   0.0050\n"
        "  0.5000   0.0500\n"
        "  0.0000   0.0000\n"
        "  0.5000  -0.0500\n"
        "  1.0000  -0.0050\n"
    )

    dat_file = tmp_path / "test_airfoil.dat"
    dat_file.write_text(dat_content)

    geom = parse_dat_file(dat_file)

    assert geom.name == "Test Airfoil"
    assert geom.coordinates.shape == (5, 2)
    assert np.isclose(geom.coordinates[0, 0], 1.0)
    assert np.isclose(geom.coordinates[2, 0], 0.0)

    # Thickness should be max(y_upper - y_lower) ≈ 0.10 at x=0.5
    assert geom.thickness_ratio == pytest.approx(0.10, abs=0.01)


# ---------------------------------------------------------------------------
# Unit test: caching behaviour
# ---------------------------------------------------------------------------

from unittest.mock import patch

@pytest.mark.network
def test_fetch_caches_file(tmp_path: Path):
    """Second fetch should use cached file, not re-download."""
    cache = tmp_path / "airfoil_cache"
    from unittest.mock import MagicMock

    def mock_urlopen(url):
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b"Mock Airfoil\n"
            b"  1.0000   0.0000\n"
            b"  0.7500   0.0300\n"
            b"  0.5000   0.0500\n"
            b"  0.2500   0.0300\n"
            b"  0.0000   0.0000\n"
            b"  0.2500  -0.0300\n"
            b"  0.5000  -0.0500\n"
            b"  0.7500  -0.0300\n"
            b"  1.0000   0.0000\n"
        )
        mock_response.__enter__.return_value = mock_response
        return mock_response

    with patch("airfoil_engine.uiuc_parser.urlopen", side_effect=mock_urlopen) as mock_open:
        # First fetch — downloads (triggers mock_urlopen which returns the mock response bytes)
        geom1 = fetch_airfoil("n0012", cache_dir=cache)
        dat_file = cache / "n0012.dat"
        assert dat_file.exists(), "File should be cached after first fetch"
        mtime1 = dat_file.stat().st_mtime
        assert mock_open.call_count == 1

        # Second fetch — should use cache (same mtime)
        geom2 = fetch_airfoil("n0012", cache_dir=cache)
        mtime2 = dat_file.stat().st_mtime
        assert mock_open.call_count == 1

        assert mtime1 == mtime2, "Cached file should not be re-downloaded"
        assert geom1.name == geom2.name
        assert geom1.thickness_ratio == pytest.approx(geom2.thickness_ratio, abs=1e-6)



# ---------------------------------------------------------------------------
# Unit test: validate_dat_file
# ---------------------------------------------------------------------------

def test_validate_dat_file(tmp_path: Path):
    """Verify validate_dat_file detects valid/invalid airfoil data."""
    # 1. Non-existent file
    assert not validate_dat_file(tmp_path / "nonexistent.dat")

    # 2. Sane valid Selig file
    valid_content = (
        "Valid Airfoil\n"
        "  1.0000   0.0050\n"
        "  0.7500   0.0350\n"
        "  0.5000   0.0500\n"
        "  0.2500   0.0350\n"
        "  0.0000   0.0000\n"
        "  0.2500  -0.0350\n"
        "  0.5000  -0.0500\n"
        "  0.7500  -0.0350\n"
        "  1.0000  -0.0050\n"
    )
    valid_file = tmp_path / "valid.dat"
    valid_file.write_text(valid_content)
    assert validate_dat_file(valid_file)

    # 3. Too few points
    too_few_content = (
        "Too Few Points\n"
        "  1.0000   0.0050\n"
        "  0.0000   0.0000\n"
        "  1.0000  -0.0050\n"
    )
    too_few_file = tmp_path / "too_few.dat"
    too_few_file.write_text(too_few_content)
    assert not validate_dat_file(too_few_file)

    # 4. Out-of-bounds coordinates (x > 1.05 or y > 0.5)
    out_of_bounds_content = (
        "Out of Bounds\n"
        "  1.0000   0.0050\n"
        "  0.5000   0.6000\n"  # y = 0.6 is too high
        "  0.0000   0.0000\n"
        "  0.5000  -0.0500\n"
        "  1.0000  -0.0050\n"
        "  0.5000   0.0500\n"
        "  0.2500   0.0350\n"
        "  0.2500  -0.0350\n"
        "  0.7500   0.0200\n"
        "  0.7500  -0.0200\n"
    )
    out_of_bounds_file = tmp_path / "out_of_bounds.dat"
    out_of_bounds_file.write_text(out_of_bounds_content)
    assert not validate_dat_file(out_of_bounds_file)

    # 5. Bad chord length
    bad_chord_content = (
        "Bad Chord\n"
        "  0.5000   0.0050\n"  # max x is 0.5, so chord is 0.5 (should be ~1.0)
        "  0.2500   0.0500\n"
        "  0.0000   0.0000\n"
        "  0.2500  -0.0500\n"
        "  0.5000  -0.0050\n"
        "  0.1000   0.0100\n"
        "  0.1000  -0.0100\n"
        "  0.3000   0.0200\n"
        "  0.3000  -0.0200\n"
        "  0.4000   0.0100\n"
    )
    bad_chord_file = tmp_path / "bad_chord.dat"
    bad_chord_file.write_text(bad_chord_content)
    assert not validate_dat_file(bad_chord_file)


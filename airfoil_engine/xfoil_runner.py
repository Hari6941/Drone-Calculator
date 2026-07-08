"""
xfoil_runner.py

Subprocess wrapper that drives XFOIL for viscous airfoil analysis.

Runs XFOIL as an external process, feeds it commands via stdin,
and parses the polar accumulation output file.

Reference:
    Drela, M., "XFOIL: An Analysis and Design System for Low Reynolds
    Number Airfoils", Conference on Low Reynolds Number Airfoil
    Aerodynamics, University of Notre Dame, 1989.

All units are SI where applicable; angles in degrees.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PolarResult:
    """Result of an XFOIL viscous polar analysis.

    Attributes:
        alpha: Angle of attack array, degrees.
        CL: Lift coefficient array.
        CD: Drag coefficient array.
        CM: Pitching moment coefficient array.
        Re: Reynolds number used for the analysis.
        airfoil_id: Identifier string for the airfoil.

    Reference:
        Drela, M., "XFOIL: An Analysis and Design System for Low
        Reynolds Number Airfoils", 1989.
    """
    alpha: np.ndarray
    CL: np.ndarray
    CD: np.ndarray
    CM: np.ndarray
    Re: float
    airfoil_id: str

    @property
    def CL_max(self) -> float:
        """Maximum lift coefficient in the polar."""
        if len(self.CL) == 0:
            raise ValueError("Empty polar — no CL data")
        return float(np.max(self.CL))

    @property
    def CD_min(self) -> float:
        """Minimum drag coefficient (where CD > 0)."""
        if len(self.CD) == 0:
            raise ValueError("Empty polar — no CD data")
        positive = self.CD[self.CD > 0]
        if len(positive) == 0:
            raise ValueError("No positive CD values in polar")
        return float(np.min(positive))

    @property
    def L_D_max(self) -> float:
        """Maximum lift-to-drag ratio in the polar."""
        if len(self.CL) == 0 or len(self.CD) == 0:
            raise ValueError("Empty polar — no data")
        valid = self.CD > 0
        if not np.any(valid):
            raise ValueError("No positive CD values in polar")
        ratios = self.CL[valid] / self.CD[valid]
        return float(np.max(ratios))

    @property
    def alpha_at_CL_max(self) -> float:
        """Angle of attack at maximum CL, degrees."""
        if len(self.CL) == 0:
            raise ValueError("Empty polar — no CL data")
        return float(self.alpha[np.argmax(self.CL)])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_xfoil_path(xfoil_path: str | None) -> str:
    """Resolve the XFOIL executable path.

    Priority: explicit argument → XFOIL_PATH env var → 'xfoil' on PATH.

    Args:
        xfoil_path: Explicit path, or None.

    Returns:
        Resolved executable path string.
    """
    if xfoil_path is not None:
        return xfoil_path

    env_path = os.environ.get("XFOIL_PATH")
    if env_path:
        return env_path

    return "xfoil"


def _parse_polar_file(
    path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Parse an XFOIL polar accumulation file.

    The file has a multi-line header followed by data columns:
        alpha  CL  CD  CDp  CM  Top_Xtr  Bot_Xtr

    We extract columns 0 (alpha), 1 (CL), 2 (CD), 4 (CM).

    Args:
        path: Path to the polar output file.

    Returns:
        Tuple of (alpha, CL, CD, CM) as 1-D numpy arrays.

    Raises:
        RuntimeError: If no data rows are found.
    """
    alpha_list: list[float] = []
    cl_list: list[float] = []
    cd_list: list[float] = []
    cm_list: list[float] = []

    in_data = False

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Detect the separator line that precedes data
            if stripped.startswith("------"):
                in_data = True
                continue

            if not in_data:
                continue

            # Try to parse as data row
            parts = stripped.split()
            if len(parts) < 5:
                continue

            try:
                vals = [float(p) for p in parts]
            except ValueError:
                continue

            # Columns: alpha(0) CL(1) CD(2) CDp(3) CM(4) Top_Xtr(5) Bot_Xtr(6)
            alpha_list.append(vals[0])
            cl_list.append(vals[1])
            cd_list.append(vals[2])
            cm_list.append(vals[4])

    if not alpha_list:
        raise RuntimeError(
            f"No data rows found in polar file: {path}"
        )

    return (
        np.array(alpha_list, dtype=np.float64),
        np.array(cl_list, dtype=np.float64),
        np.array(cd_list, dtype=np.float64),
        np.array(cm_list, dtype=np.float64),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_xfoil(
    dat_file: Path,
    Re: float,
    alpha_start: float = -5.0,
    alpha_end: float = 15.0,
    alpha_step: float = 0.5,
    ncrit: float = 9.0,
    max_iter: int = 200,
    timeout_s: float = 120.0,
    xfoil_path: str | None = None,
) -> PolarResult:
    """Run XFOIL viscous analysis for an airfoil and return the polar.

    Drives XFOIL as a subprocess: loads the airfoil coordinates,
    enables viscous mode at the specified Reynolds number, sweeps
    angle of attack, and collects CL/CD/CM via polar accumulation.

    Reference:
        Drela, M., "XFOIL: An Analysis and Design System for Low
        Reynolds Number Airfoils", Conference on Low Reynolds Number
        Airfoil Aerodynamics, University of Notre Dame, 1989.

    Args:
        dat_file: Path to the airfoil .dat coordinate file.
        Re: Reynolds number (e.g. 200_000).
        alpha_start: Starting angle of attack, degrees.
        alpha_end: Ending angle of attack, degrees.
        alpha_step: AoA increment, degrees.
        ncrit: Critical amplification ratio for e^N transition model.
            Default 9.0 (standard wind tunnel turbulence).
        max_iter: Maximum XFOIL iterations per operating point.
        timeout_s: Subprocess timeout in seconds.
        xfoil_path: Path to xfoil executable. Resolved via:
            explicit arg → XFOIL_PATH env var → 'xfoil' on PATH.

    Returns:
        PolarResult with alpha, CL, CD, CM arrays.

    Raises:
        FileNotFoundError: If the XFOIL binary or .dat file is not found.
        subprocess.TimeoutExpired: If XFOIL exceeds timeout_s.
        RuntimeError: If XFOIL produces no converged data points.
    """
    dat_file = Path(dat_file).resolve()
    if not dat_file.exists():
        raise FileNotFoundError(f"Airfoil .dat file not found: {dat_file}")

    xfoil_bin = _resolve_xfoil_path(xfoil_path)
    airfoil_id = dat_file.stem

    # Create temp directory for polar output (inside project workspace)
    tmp_dir = Path(tempfile.mkdtemp(prefix="xfoil_"))
    polar_file = (tmp_dir / "polar.txt").resolve()

    try:
        # Build XFOIL command sequence as a single string with explicit
        # newlines. The PLOP → G → blank-line preamble disables the
        # graphics/plotting device (PltLib) BEFORE any airfoil is loaded,
        # preventing interactive plot windows that would block the process.
        #
        # Reference for PLOP G:
        #   XFOIL 6.96+ documentation; "G" toggles the graphic output flag
        #   inside the PLOP (PLot OPtions) submenu.
        commands = (
            "PLOP\n"
            "G\n"              # toggle graphics OFF
            "\n"               # exit PLOP menu
            f"LOAD {dat_file}\n"
            "OPER\n"
            f"VISC {Re:.0f}\n"
            "VPAR\n"
            f"N {ncrit:.1f}\n"
            "\n"               # exit VPAR submenu
            f"ITER {max_iter}\n"
            "PACC\n"
            f"{polar_file}\n"
            "\n"               # no dump file
            f"ASEQ {alpha_start:.2f} {alpha_end:.2f} {alpha_step:.2f}\n"
            "\n"               # blank line after ASEQ completes
            "PACC\n"
            "\n"
            "QUIT\n"
        )

        logger.info(
            "Running XFOIL: %s, Re=%.0f, alpha=[%.1f, %.1f, %.1f], ncrit=%.1f",
            airfoil_id, Re, alpha_start, alpha_end, alpha_step, ncrit,
        )

        try:
            # Prevent XFOIL from initialising any graphics backend:
            #  - Remove DISPLAY (prevents X11 on Unix/MSYS2/Cygwin)
            #  - On Windows, set CREATE_NO_WINDOW flag
            env = os.environ.copy()
            env.pop("DISPLAY", None)

            kwargs: dict = {"env": env}
            if os.name == "nt":
                kwargs["creationflags"] = (
                    subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
                )

            result = subprocess.run(
                [xfoil_bin],
                input=commands,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(dat_file.parent),
                **kwargs,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"XFOIL executable not found: '{xfoil_bin}'. "
                f"Set XFOIL_PATH env var or add xfoil to PATH."
            )
        except subprocess.TimeoutExpired:
            raise subprocess.TimeoutExpired(
                cmd=xfoil_bin,
                timeout=timeout_s,
                output=f"XFOIL timed out after {timeout_s}s "
                       f"analysing {airfoil_id} at Re={Re:.0f}",
            )

        # Check if polar file was created
        if not polar_file.exists() or polar_file.stat().st_size == 0:
            logger.error("XFOIL stdout:\n%s", result.stdout[-2000:] if result.stdout else "(empty)")
            logger.error("XFOIL stderr:\n%s", result.stderr[-2000:] if result.stderr else "(empty)")
            raise RuntimeError(
                f"XFOIL produced no converged points for {airfoil_id} "
                f"at Re={Re:.0f}. Check that the .dat file is valid."
            )

        # Parse the polar output
        alpha, CL, CD, CM = _parse_polar_file(polar_file)

        logger.info(
            "XFOIL converged %d points for %s: CL=[%.3f, %.3f], CD=[%.5f, %.5f]",
            len(alpha), airfoil_id,
            float(np.min(CL)), float(np.max(CL)),
            float(np.min(CD)), float(np.max(CD)),
        )

        return PolarResult(
            alpha=alpha,
            CL=CL,
            CD=CD,
            CM=CM,
            Re=Re,
            airfoil_id=airfoil_id,
        )

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmp_dir)
        except OSError as exc:
            logger.warning("Failed to clean up temp dir %s: %s", tmp_dir, exc)

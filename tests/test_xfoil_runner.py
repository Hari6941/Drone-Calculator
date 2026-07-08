"""
test_xfoil_runner.py

Tests for the XFOIL subprocess wrapper.

Validation cases sourced from:
    Selig, M. S., et al., "Summary of Low-Speed Airfoil Data",
    Vols. 1–5, SoarTech Publications / UIUC wind tunnel measurements.

    NACA 0012 @ Re=200,000:  CL_max ≈ 0.90–0.95,  CD_min ≈ 0.0095–0.011
    Clark Y   @ Re=200,000:  CL_max ≈ 1.10–1.25,  CD_min ≈ 0.010–0.013

Run with:  pytest tests/test_xfoil_runner.py -v -s   (use -s for diff reports)
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from airfoil_engine.xfoil_runner import PolarResult, run_xfoil


# ---------------------------------------------------------------------------
# Skip decorator for tests that require XFOIL
# ---------------------------------------------------------------------------

xfoil_available = (
    shutil.which("xfoil") is not None
    or os.environ.get("XFOIL_PATH") is not None
)

skip_no_xfoil = pytest.mark.skipif(
    not xfoil_available,
    reason="XFOIL not found on PATH or XFOIL_PATH",
)


# ---------------------------------------------------------------------------
# Helper: print validation diff report
# ---------------------------------------------------------------------------

def _print_diff_report(
    name: str,
    Re: float,
    cl_max_xfoil: float,
    cl_max_pub: float,
    cd_min_xfoil: float,
    cd_min_pub: float,
) -> None:
    """Print a formatted comparison of XFOIL output vs published data."""
    cl_diff_pct = (cl_max_xfoil - cl_max_pub) / cl_max_pub * 100
    cd_diff_pct = (cd_min_xfoil - cd_min_pub) / cd_min_pub * 100

    print(f"\n{'='*60}")
    print(f"  {name} @ Re={Re:,.0f} — Validation Report")
    print(f"{'='*60}")
    print(f"  CL_max: XFOIL={cl_max_xfoil:.4f}  "
          f"Published={cl_max_pub:.4f}  "
          f"Diff={cl_diff_pct:+.1f}%")
    print(f"  CD_min: XFOIL={cd_min_xfoil:.6f}  "
          f"Published={cd_min_pub:.6f}  "
          f"Diff={cd_diff_pct:+.1f}%")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Validation case 1: NACA 0012 at Re = 200,000
# Source: Selig et al., "Summary of Low-Speed Airfoil Data"
#   CL_max ≈ 0.90–0.95 (midpoint 0.925)
#   CD_min ≈ 0.0095–0.011 (midpoint 0.01025)
# ---------------------------------------------------------------------------

@skip_no_xfoil
@pytest.mark.network
def test_naca0012_polar():
    """XFOIL NACA 0012 @ Re=200k vs published UIUC wind tunnel data."""
    from airfoil_engine.uiuc_parser import fetch_airfoil

    geom = fetch_airfoil("n0012")
    dat_path = (
        Path(__file__).resolve().parent.parent
        / "data" / "airfoils" / "n0012.dat"
    )

    polar = run_xfoil(dat_path, Re=200_000, alpha_start=-5, alpha_end=15, alpha_step=0.5)

    # Published midpoints
    cl_max_pub = 0.925    # midpoint of [0.90, 0.95]
    cd_min_pub = 0.01025  # midpoint of [0.0095, 0.011]

    _print_diff_report(
        "NACA 0012", 200_000,
        polar.CL_max, cl_max_pub,
        polar.CD_min, cd_min_pub,
    )

    # CL_max: ±20% tolerance — XFOIL's e^N transition model is documented
    # to overpredict CL_max by ~15-20% at Re≈200k due to incomplete
    # capture of laminar separation bubble behavior. This is a known
    # XFOIL limitation, not a code defect.
    assert polar.CL_max == pytest.approx(cl_max_pub, rel=0.20), (
        f"CL_max={polar.CL_max:.4f} outside ±20% of {cl_max_pub}"
    )
    # CD_min: ±15% tolerance — XFOIL drag prediction matches published
    # experimental data well at this Reynolds number.
    assert polar.CD_min == pytest.approx(cd_min_pub, rel=0.15), (
        f"CD_min={polar.CD_min:.6f} outside ±15% of {cd_min_pub}"
    )

    # Sanity checks
    assert len(polar.alpha) > 10, "Expected >10 converged points"
    assert polar.airfoil_id == "n0012"
    assert polar.Re == 200_000


# ---------------------------------------------------------------------------
# Validation case 2: Clark Y at Re = 200,000
# Source: Selig et al., "Summary of Low-Speed Airfoil Data"
#   CL_max ≈ 1.10–1.25 (midpoint 1.175)
#   CD_min ≈ 0.010–0.013 (midpoint 0.0115)
# ---------------------------------------------------------------------------

@skip_no_xfoil
@pytest.mark.network
def test_clarky_polar():
    """XFOIL Clark Y @ Re=200k vs published UIUC wind tunnel data."""
    from airfoil_engine.uiuc_parser import fetch_airfoil

    geom = fetch_airfoil("clarky")
    dat_path = (
        Path(__file__).resolve().parent.parent
        / "data" / "airfoils" / "clarky.dat"
    )

    polar = run_xfoil(dat_path, Re=200_000, alpha_start=-5, alpha_end=15, alpha_step=0.5)

    # Published midpoints
    cl_max_pub = 1.175   # midpoint of [1.10, 1.25]
    cd_min_pub = 0.0115  # midpoint of [0.010, 0.013]

    _print_diff_report(
        "Clark Y", 200_000,
        polar.CL_max, cl_max_pub,
        polar.CD_min, cd_min_pub,
    )

    # CL_max: ±20% tolerance — XFOIL's e^N transition model is documented
    # to overpredict CL_max by ~15-20% at Re≈200k due to incomplete
    # capture of laminar separation bubble behavior. This is a known
    # XFOIL limitation, not a code defect.
    assert polar.CL_max == pytest.approx(cl_max_pub, rel=0.20), (
        f"CL_max={polar.CL_max:.4f} outside ±20% of {cl_max_pub}"
    )
    # CD_min: ±15% tolerance — XFOIL drag prediction matches published
    # experimental data well at this Reynolds number.
    assert polar.CD_min == pytest.approx(cd_min_pub, rel=0.15), (
        f"CD_min={polar.CD_min:.6f} outside ±15% of {cd_min_pub}"
    )

    assert len(polar.alpha) > 10
    assert polar.airfoil_id == "clarky"


# ---------------------------------------------------------------------------
# Unit test: PolarResult computed properties
# ---------------------------------------------------------------------------

def test_polar_result_properties():
    """Verify PolarResult properties with hand-computed values."""
    alpha = np.array([-2.0, 0.0, 2.0, 5.0, 10.0, 12.0])
    CL = np.array([-0.1, 0.1, 0.3, 0.6, 0.95, 0.90])
    CD = np.array([0.012, 0.010, 0.011, 0.014, 0.025, 0.035])
    CM = np.array([-0.01, -0.01, -0.02, -0.03, -0.05, -0.06])

    polar = PolarResult(
        alpha=alpha, CL=CL, CD=CD, CM=CM,
        Re=200_000, airfoil_id="test",
    )

    # CL_max = 0.95 at alpha = 10.0
    assert polar.CL_max == pytest.approx(0.95)
    assert polar.alpha_at_CL_max == pytest.approx(10.0)

    # CD_min = 0.010 (at alpha=0)
    assert polar.CD_min == pytest.approx(0.010)

    # L/D_max = max(CL/CD) = max(-0.1/0.012, 0.1/0.010, 0.3/0.011, ...)
    # 0.3/0.011 ≈ 27.27, 0.6/0.014 ≈ 42.86, 0.95/0.025 = 38.0
    expected_ld_max = 0.6 / 0.014  # ≈ 42.857
    assert polar.L_D_max == pytest.approx(expected_ld_max, rel=1e-3)


# ---------------------------------------------------------------------------
# Unit test: XFOIL not found
# ---------------------------------------------------------------------------

def test_xfoil_not_found(tmp_path: Path):
    """run_xfoil should raise FileNotFoundError for missing binary."""
    # Create a dummy .dat file
    dat_file = tmp_path / "dummy.dat"
    dat_file.write_text("Dummy Airfoil\n1.0 0.0\n0.5 0.05\n0.0 0.0\n0.5 -0.05\n1.0 0.0\n")

    with pytest.raises(FileNotFoundError, match="XFOIL executable not found"):
        run_xfoil(
            dat_file,
            Re=200_000,
            xfoil_path="nonexistent_binary_xyz_42",
        )

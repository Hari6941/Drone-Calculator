"""
test_filter.py

Tests for the airfoil filter/ranker.

Validation cases:
    1. Clark Y should rank above NACA 0012 at CL_cruise=0.5, Re=200k
       (better L/D and more CL margin).
    2. NACA 0012 should be filtered out when CL_cruise=0.8 with 0.3 margin
       (CL_max ≈ 0.9–0.95, giving margin ≈ 0.1–0.15 < 0.3).
    3. Interpolation unit test with synthetic data.
    4. Thickness constraint filter.

Run with:  pytest tests/test_filter.py -v -s
"""

from __future__ import annotations

import os
import shutil

import numpy as np
import pytest

from airfoil_engine.filter import AirfoilCandidate, _interpolate_CD_at_CL, filter_airfoils
from airfoil_engine.xfoil_runner import PolarResult


# ---------------------------------------------------------------------------
# Skip decorator for XFOIL-dependent tests
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
# Validation case 1: Clark Y should rank above NACA 0012
# at CL_cruise=0.5, Re=200,000
# ---------------------------------------------------------------------------

@skip_no_xfoil
@pytest.mark.network
def test_clarky_ranks_above_naca0012():
    """Clark Y should score higher than NACA 0012 at CL_cruise=0.5."""
    results = filter_airfoils(
        candidates=["n0012", "clarky"],
        CL_cruise=0.5,
        Re=200_000,
    )

    assert len(results) == 2, (
        f"Expected 2 passing candidates, got {len(results)}: "
        f"{[r.airfoil_id for r in results]}"
    )

    # Clark Y should be first (highest score)
    assert results[0].airfoil_id == "clarky", (
        f"Expected clarky first, got {results[0].airfoil_id} "
        f"(scores: {[(r.airfoil_id, r.score) for r in results]})"
    )

    # All scores should be positive
    for r in results:
        assert r.score > 0, f"{r.airfoil_id} has non-positive score {r.score}"

    # Print ranking for inspection
    print("\nFilter ranking (CL_cruise=0.5, Re=200,000):")
    for i, r in enumerate(results):
        print(
            f"  {i+1}. {r.airfoil_id:12s}  "
            f"score={r.score:.2f}  L/D={r.L_D_at_CL_cruise:.1f}  "
            f"CL_max={r.CL_max:.3f}  CD={r.CD_at_CL_cruise:.5f}  "
            f"t/c={r.thickness_ratio:.3f}"
        )


# ---------------------------------------------------------------------------
# Validation case 2: NACA 0012 filtered out at CL_cruise=0.8
# (CL_max ≈ 0.9–0.95, margin ≈ 0.1–0.15 < required 0.3)
# ---------------------------------------------------------------------------

@skip_no_xfoil
@pytest.mark.network
def test_filter_removes_low_clmax():
    """NACA 0012 should be filtered out when CL_cruise=0.8, min_CL_margin=0.3."""
    results = filter_airfoils(
        candidates=["n0012"],
        CL_cruise=0.8,
        Re=200_000,
        min_CL_margin=0.3,
    )

    assert len(results) == 0, (
        f"Expected NACA 0012 to be filtered out, but got: "
        f"{[r.airfoil_id for r in results]}"
    )


# ---------------------------------------------------------------------------
# Unit test: _interpolate_CD_at_CL with synthetic data
# ---------------------------------------------------------------------------

def test_interpolate_CD_at_CL():
    """Interpolation on synthetic polar data with known values."""
    polar = PolarResult(
        alpha=np.array([0.0, 5.0, 10.0]),
        CL=np.array([0.0, 0.5, 1.0]),
        CD=np.array([0.010, 0.015, 0.030]),
        CM=np.array([-0.01, -0.02, -0.03]),
        Re=200_000,
        airfoil_id="synthetic",
    )

    # Interpolate at CL=0.25 → midpoint between (0.0, 0.010) and (0.5, 0.015) = 0.0125
    cd = _interpolate_CD_at_CL(polar, 0.25)
    assert cd is not None
    assert cd == pytest.approx(0.0125, abs=1e-6)

    # Interpolate at CL=0.75 → midpoint between (0.5, 0.015) and (1.0, 0.030) = 0.0225
    cd = _interpolate_CD_at_CL(polar, 0.75)
    assert cd is not None
    assert cd == pytest.approx(0.0225, abs=1e-6)

    # Out of range: CL=1.5 → should return None (no extrapolation)
    cd = _interpolate_CD_at_CL(polar, 1.5)
    assert cd is None

    # Out of range: CL=-0.5 → should return None
    cd = _interpolate_CD_at_CL(polar, -0.5)
    assert cd is None


# ---------------------------------------------------------------------------
# Validation case 4: thickness constraint filters out Clark Y
# (Clark Y is ~11.7% thick, max_thickness=0.05 should exclude it)
# ---------------------------------------------------------------------------

@skip_no_xfoil
@pytest.mark.network
def test_filter_thickness_constraint():
    """Clark Y (11.7% thick) should be filtered out with max_thickness=0.05."""
    results = filter_airfoils(
        candidates=["clarky"],
        CL_cruise=0.5,
        Re=200_000,
        max_thickness=0.05,
    )

    assert len(results) == 0, (
        f"Expected Clark Y to be filtered out by thickness, but got: "
        f"{[r.airfoil_id for r in results]}"
    )

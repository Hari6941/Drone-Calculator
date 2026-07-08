"""
filter.py

Filters and ranks candidate airfoils from the UIUC database for a
given mission profile (target CL_cruise, Reynolds number).

Scoring uses a weighted merit function inspired by:
    Selig, M. S., et al., "Summary of Low-Speed Airfoil Data",
    Vols. 1–5, SoarTech Publications.

All units are SI.  Thickness ratio is dimensionless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from airfoil_engine.uiuc_parser import AirfoilGeometry, fetch_airfoil
from airfoil_engine.xfoil_runner import PolarResult, run_xfoil

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AirfoilCandidate:
    """A candidate airfoil that passed filtering and has been scored.

    Attributes:
        airfoil_id: UIUC identifier (e.g. 'clarky').
        CL_max: Maximum lift coefficient from XFOIL polar.
        CD_at_CL_cruise: Drag coefficient interpolated at CL_cruise.
        L_D_at_CL_cruise: Lift-to-drag ratio at CL_cruise.
        thickness_ratio: Maximum thickness / chord.
        score: Composite ranking score (higher is better).
    """
    airfoil_id: str
    CL_max: float
    CD_at_CL_cruise: float
    L_D_at_CL_cruise: float
    thickness_ratio: float
    score: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _interpolate_CD_at_CL(polar: PolarResult, CL_target: float) -> float | None:
    """Linear interpolation of drag coefficient at a specified lift coefficient.

    Interpolates CD from the XFOIL polar data at the target CL. Only
    interpolates within the range of CL data (no extrapolation).

    Args:
        polar: XFOIL polar result containing CL and CD arrays.
        CL_target: Target lift coefficient for interpolation.

    Returns:
        Interpolated CD value, or None if CL_target is outside
        the range of the polar data.
    """
    if len(polar.CL) == 0 or len(polar.CD) == 0:
        return None

    # Sort by CL for monotonic interpolation
    sort_idx = np.argsort(polar.CL)
    cl_sorted = polar.CL[sort_idx]
    cd_sorted = polar.CD[sort_idx]

    # Check bounds — no extrapolation
    if CL_target < cl_sorted[0] or CL_target > cl_sorted[-1]:
        return None

    cd_interp = float(np.interp(CL_target, cl_sorted, cd_sorted))
    return cd_interp


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def filter_airfoils(
    candidates: list[str],
    CL_cruise: float,
    Re: float,
    min_CL_margin: float = 0.3,
    max_thickness: float = 0.20,
    xfoil_path: str | None = None,
) -> list[AirfoilCandidate]:
    """Evaluate, filter, and rank candidate airfoils for a mission profile.

    For each candidate airfoil:
      1. Downloads/caches the .dat file from UIUC.
      2. Runs XFOIL viscous analysis at the given Reynolds number.
      3. Applies filtering criteria (stall margin, thickness, interpolation).
      4. Computes a weighted merit score.

    Scoring formula (higher is better):
        score = 1.0 × L/D_cruise  +  0.5 × CL_margin  −  0.2 × (t/c × 100)

    Where:
        L/D_cruise = CL_cruise / CD(CL_cruise)
        CL_margin  = CL_max − CL_cruise
        t/c        = thickness_ratio

    The score rewards high cruise efficiency and stall margin while
    penalising excessive thickness (structural weight proxy).

    Source: Weighted merit approach inspired by Selig, M. S., et al.,
        "Summary of Low-Speed Airfoil Data", Vols. 1–5.

    Args:
        candidates: List of UIUC airfoil IDs to evaluate.
        CL_cruise: Target cruise lift coefficient.
        Re: Operating Reynolds number.
        min_CL_margin: Minimum required CL_max − CL_cruise.
        max_thickness: Maximum allowable thickness ratio.
        xfoil_path: Path to XFOIL executable (see run_xfoil).

    Returns:
        Sorted list of AirfoilCandidate (best score first).
        Airfoils that fail filters or cause errors are excluded.
    """
    results: list[AirfoilCandidate] = []

    for airfoil_id in candidates:
        try:
            logger.info("Evaluating %s at Re=%.0f, CL_cruise=%.3f",
                        airfoil_id, Re, CL_cruise)

            # 1. Fetch geometry
            geometry = fetch_airfoil(airfoil_id)

            # 2. Thickness filter
            if geometry.thickness_ratio > max_thickness:
                logger.info(
                    "  SKIP %s: thickness %.3f > max %.3f",
                    airfoil_id, geometry.thickness_ratio, max_thickness,
                )
                continue

            # 3. Run XFOIL
            dat_path = (
                Path(__file__).resolve().parent.parent
                / "data" / "airfoils" / f"{airfoil_id}.dat"
            )
            polar = run_xfoil(dat_path, Re, xfoil_path=xfoil_path)

            # 4. CL margin filter
            cl_margin = polar.CL_max - CL_cruise
            if cl_margin < min_CL_margin:
                logger.info(
                    "  SKIP %s: CL_margin %.3f < min %.3f (CL_max=%.3f)",
                    airfoil_id, cl_margin, min_CL_margin, polar.CL_max,
                )
                continue

            # 5. Interpolate CD at cruise CL
            cd_cruise = _interpolate_CD_at_CL(polar, CL_cruise)
            if cd_cruise is None or cd_cruise <= 0:
                logger.info(
                    "  SKIP %s: could not interpolate CD at CL=%.3f",
                    airfoil_id, CL_cruise,
                )
                continue

            # 6. Compute score
            ld_cruise = CL_cruise / cd_cruise
            score = (
                1.0 * ld_cruise
                + 0.5 * cl_margin
                - 0.2 * (geometry.thickness_ratio * 100)
            )

            candidate = AirfoilCandidate(
                airfoil_id=airfoil_id,
                CL_max=polar.CL_max,
                CD_at_CL_cruise=cd_cruise,
                L_D_at_CL_cruise=ld_cruise,
                thickness_ratio=geometry.thickness_ratio,
                score=score,
            )

            logger.info(
                "  PASS %s: L/D=%.1f, CL_max=%.3f, t/c=%.3f, score=%.2f",
                airfoil_id, ld_cruise, polar.CL_max,
                geometry.thickness_ratio, score,
            )
            results.append(candidate)

        except Exception:
            logger.warning(
                "  ERROR evaluating %s — skipping", airfoil_id, exc_info=True
            )
            continue

    # Sort by score descending
    results.sort(key=lambda c: c.score, reverse=True)

    logger.info(
        "filter_airfoils: %d/%d candidates passed",
        len(results), len(candidates),
    )
    return results

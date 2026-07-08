"""
select_airfoil.py

Node to filter and select the best airfoil for the current cruise CL and Reynolds number.
"""

import logging

from agents.state import DesignState, Violation
from airfoil_engine import filter_airfoils

logger = logging.getLogger(__name__)

def select_airfoil(state: DesignState) -> dict:
    """Runs filter_airfoils to select the top candidate. Updates airfoil_id,
    CD0, and CL_max in the state.
    """
    logger.info("Filtering and selecting best airfoil...")
    
    candidates = state["candidate_airfoils"]
    CL_cruise = state["CL_cruise"]
    Re = state["Re"]

    # We run XFOIL via filter_airfoils.
    # Note: XFOIL tests/runs skip if binary is missing. If skipped/failed,
    # filter_airfoils will return an empty list or log exceptions.
    try:
        ranked_candidates = filter_airfoils(
            candidates=candidates,
            CL_cruise=CL_cruise,
            Re=Re,
            min_CL_margin=0.3,
            max_thickness=0.20,
        )
    except Exception as exc:
        logger.error("Error in filter_airfoils: %s", exc)
        ranked_candidates = []

    if ranked_candidates:
        best = ranked_candidates[0]
        logger.info(
            "Selected airfoil: %s (score=%.2f, CL_max=%.3f, CD_at_cruise=%.5f)",
            best.airfoil_id, best.score, best.CL_max, best.CD_at_CL_cruise,
        )
        return {
            "airfoil_id": best.airfoil_id,
            "CD0": best.CD_at_CL_cruise,
            "CL_max": best.CL_max,
        }
    else:
        # Fallback if no airfoils converged/passed
        logger.warning(
            "No airfoils passed filter for CL_cruise=%.3f at Re=%.0f",
            CL_cruise, Re
        )
        
        # We don't overwrite airfoil_id/CD0/CL_max if they exist in state,
        # but if this is the first run, we initialize them.
        fallback_id = state.get("airfoil_id", "clarky")
        fallback_CD0 = state.get("CD0", 0.025)
        fallback_CL_max = state.get("CL_max", 1.2)
        
        return {
            "airfoil_id": fallback_id,
            "CD0": fallback_CD0,
            "CL_max": fallback_CL_max,
        }

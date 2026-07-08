"""
evaluate_aero.py

Node to calculate flight mechanics and aerodynamic performance using physics_engine.
"""

import logging
import numpy as np

from agents.state import DesignState
from physics_engine import compute_design_point

logger = logging.getLogger(__name__)

def evaluate_aero(state: DesignState) -> dict:
    """Invokes physics_engine to calculate performance parameters (CL_cruise, CD_total,
    stall_speed_ms, L_D_ratio, power_required_W, etc.) and computes Reynolds number.
    """
    logger.info("Evaluating aerodynamic and performance equations...")
    
    inputs = {
        "MTOW_kg": state["MTOW_kg"],
        "V_cruise_ms": state["V_cruise_ms"],
        "rho": state["rules"].rho,
        "S_m2": state["S_m2"],
        "AR": state["AR"],
        "e": state["e"],
        "CD0": state["CD0"],
        "CL_max": state["CL_max"],
    }

    try:
        perf = compute_design_point(inputs)
    except Exception as exc:
        logger.error("Error running compute_design_point: %s", exc)
        raise exc

    # Calculate span and aspect ratio for consistency
    AR = state["AR"]
    S_m2 = state["S_m2"]
    span_m = float(np.sqrt(AR * S_m2))

    # Calculate Reynolds number (Re = rho * V * c / mu)
    # Dynamic viscosity of air at 15C (ISA standard) is approximately 1.789e-5 Pa s
    mu = 1.789e-5
    chord_m = S_m2 / span_m if span_m > 0 else 0.1
    Re = (state["rules"].rho * state["V_cruise_ms"] * chord_m) / mu

    # Update states
    updates = {
        "wing_area_m2": perf["wing_area_m2"],
        "CL_cruise": perf["CL_cruise"],
        "CD_total": perf["CD_total"],
        "stall_speed_ms": perf["stall_speed_ms"],
        "L_D_ratio": perf["L_D_ratio"],
        "power_required_W": perf["power_required_W"],
        "span_m": span_m,
        "aspect_ratio": AR,
        "Re": Re,
    }
    
    logger.info(
        "Performance: CL_cruise=%.3f, CD_total=%.5f, L/D=%.1f, stall_speed=%.1f m/s, power=%.1f W, Re=%.0f",
        perf["CL_cruise"], perf["CD_total"], perf["L_D_ratio"],
        perf["stall_speed_ms"], perf["power_required_W"], Re,
    )
    
    return updates

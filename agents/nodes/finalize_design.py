"""
finalize_design.py

Node to package and validate the final design output containing all AGENTS.md keys.
"""

import logging
from agents.state import DesignState

logger = logging.getLogger(__name__)

def finalize_design(state: DesignState) -> dict:
    """Packages and validates the final design configuration, confirming that
    all 10 AGENTS.md shared keys are set.
    """
    logger.info("Finalizing and validating design...")

    shared_keys = [
        "wing_area_m2",
        "aspect_ratio",
        "airfoil_id",
        "CL_cruise",
        "CD_total",
        "MTOW_kg",
        "stall_speed_ms",
        "L_D_ratio",
        "span_m",
        "power_required_W",
    ]

    missing = [k for k in shared_keys if k not in state]
    if missing:
        logger.warning("Final state is missing some AGENTS.md shared keys: %s", missing)

    # Output only the updates we want to commit (in LangGraph, the final return dictionary
    # updates the state).
    # Since we want to return the state dict or let the user access the full state from the graph run:
    # We will log the summary of the final design.
    logger.info("=" * 60)
    logger.info("  FINAL DESIGN SPECIFICATION")
    logger.info("=" * 60)
    logger.info("  MTOW (kg):          %.3f", state.get("MTOW_kg", 0.0))
    logger.info("  Wing Area (m^2):    %.4f", state.get("wing_area_m2", 0.0))
    logger.info("  Aspect Ratio:       %.2f", state.get("aspect_ratio", 0.0))
    logger.info("  Wingspan (m):       %.3f", state.get("span_m", 0.0))
    logger.info("  Selected Airfoil:   %s", state.get("airfoil_id", "None"))
    logger.info("  Cruise CL:          %.3f", state.get("CL_cruise", 0.0))
    logger.info("  CD Total:           %.5f", state.get("CD_total", 0.0))
    logger.info("  L/D Ratio:          %.2f", state.get("L_D_ratio", 0.0))
    logger.info("  Stall Speed (m/s):  %.2f", state.get("stall_speed_ms", 0.0))
    logger.info("  Power Required (W): %.1f", state.get("power_required_W", 0.0))
    logger.info("  Converged:          %s", state.get("converged", False))
    logger.info("  Iterations:         %d", state.get("iteration", 0))
    logger.info("=" * 60)

    return {
        "converged": state["converged"],
        "reasoning": f"Design optimization finished. Status: {'Converged' if state['converged'] else 'Failed to converge'}.",
    }

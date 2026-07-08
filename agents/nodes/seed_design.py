"""
seed_design.py

Node to calculate initial sizing estimates for the UAV design.
"""

import logging
import numpy as np

from agents.state import DesignState
from physics_engine import G

logger = logging.getLogger(__name__)

def seed_design(state: DesignState) -> dict:
    """Sets initial design variables (S_m2, AR, V_cruise_ms, e, CD0, CL_max)
    based on standard aerospace sizing heuristics.
    """
    logger.info("Initializing design sizing (seeding)...")
    rules = state["rules"]
    MTOW_kg = state["MTOW_kg"]
    
    # 1. Cruise speed is initially set to target cruise speed
    V_cruise_ms = rules.V_cruise_target_ms

    # 2. Sizing S_m2: Lift = Weight -> S_m2 = 2*W / (rho * V^2 * CL_target)
    # Assume a target CL_cruise of 0.5 for clean initialization
    CL_target = 0.5
    W = MTOW_kg * G
    S_m2 = (2 * W) / (rules.rho * V_cruise_ms**2 * CL_target)
    
    # Apply safety clamps on S_m2
    S_m2 = max(0.05, min(S_m2, 5.0))

    # 3. Aspect Ratio: target standard small-UAV AR of 6.0,
    # but constrained by wingspan limit
    span_limit = rules.wingspan_limit_m
    # AR = span^2 / S -> limit AR by span_limit
    AR_limit = (span_limit ** 2) / S_m2
    AR = min(8.0, max(3.0, AR_limit * 0.9))  # Start at 90% of the limit or cap at 8.0

    span_m = np.sqrt(AR * S_m2)
    
    # Default initial assumptions
    e = 0.80
    CD0 = 0.025
    CL_max = 1.2

    logger.info(
        "Initial Seed: V_cruise=%.1f m/s, S_m2=%.3f, AR=%.1f, span=%.2f m",
        V_cruise_ms, S_m2, AR, span_m,
    )

    return {
        "V_cruise_ms": V_cruise_ms,
        "S_m2": S_m2,
        "AR": AR,
        "aspect_ratio": AR,
        "span_m": span_m,
        "e": e,
        "CD0": CD0,
        "CL_max": CL_max,
    }

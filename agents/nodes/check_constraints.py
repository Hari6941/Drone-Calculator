"""
check_constraints.py

Node to check current design parameters against competition rules and generate violations.
"""

import logging
from agents.state import DesignState, Violation

logger = logging.getLogger(__name__)

def check_constraints(state: DesignState) -> dict:
    """Evaluates the design against limits. Updates the violations list, history,
    and sets the converged flag.
    """
    logger.info("Checking design constraints...")
    
    rules = state["rules"]
    violations = []

    # 1. Wingspan limit check
    span = state["span_m"]
    span_limit = rules.wingspan_limit_m
    if span > span_limit:
        severity = (span - span_limit) / span_limit
        violations.append(Violation(
            parameter="span_m",
            limit=span_limit,
            actual=span,
            severity=severity,
            suggestion=f"Wingspan {span:.3f} m exceeds limit {span_limit:.2f} m by {severity*100:.1f}%. Reduce AR or S_m2."
        ))

    # 2. Stall speed limit check
    stall_speed = state["stall_speed_ms"]
    if rules.stall_speed_limit_ms is not None:
        stall_limit = rules.stall_speed_limit_ms
        if stall_speed > stall_limit:
            severity = (stall_speed - stall_limit) / stall_limit
            violations.append(Violation(
                parameter="stall_speed_ms",
                limit=stall_limit,
                actual=stall_speed,
                severity=severity,
                suggestion=f"Stall speed {stall_speed:.2f} m/s exceeds limit {stall_limit:.2f} m/s by {severity*100:.1f}%. Increase S_m2 or CL_max."
            ))

    # 3. Power limit check
    power = state["power_required_W"]
    if rules.power_limit_W is not None:
        power_limit = rules.power_limit_W
        if power > power_limit:
            severity = (power - power_limit) / power_limit
            violations.append(Violation(
                parameter="power_required_W",
                limit=power_limit,
                actual=power,
                severity=severity,
                suggestion=f"Power required {power:.1f} W exceeds limit {power_limit:.1f} W by {severity*100:.1f}%. Reduce cruise speed, S_m2, or drag (CD0)."
            ))

    # 4. CL cruise safety limit check (must be below 0.8 * CL_max)
    cl_cruise = state["CL_cruise"]
    cl_max = state["CL_max"]
    cl_limit = 0.8 * cl_max
    if cl_cruise > cl_limit:
        severity = (cl_cruise - cl_limit) / cl_limit
        violations.append(Violation(
            parameter="CL_cruise",
            limit=cl_limit,
            actual=cl_cruise,
            severity=severity,
            suggestion=f"Cruise CL {cl_cruise:.3f} is too close to stall safety limit {cl_limit:.3f} (CL_max={cl_max:.3f}). Increase S_m2 or V_cruise_ms."
        ))

    # 5. Airfoil CL margin safety check (CL_max - CL_cruise >= 0.3)
    margin = cl_max - cl_cruise
    if margin < 0.3:
        severity = (0.3 - margin) / 0.3
        violations.append(Violation(
            parameter="CL_margin",
            limit=0.3,
            actual=margin,
            severity=severity,
            suggestion=f"Airfoil CL margin {margin:.3f} is below required 0.3 (CL_max={cl_max:.3f}). Increase S_m2 or V_cruise_ms."
        ))

    # Update convergence status
    converged = len(violations) == 0

    # Save iteration history snapshot
    snapshot = {
        "wing_area_m2": state["wing_area_m2"],
        "aspect_ratio": state["aspect_ratio"],
        "airfoil_id": state["airfoil_id"],
        "CL_cruise": state["CL_cruise"],
        "CD_total": state["CD_total"],
        "MTOW_kg": state["MTOW_kg"],
        "stall_speed_ms": state["stall_speed_ms"],
        "L_D_ratio": state["L_D_ratio"],
        "span_m": state["span_m"],
        "power_required_W": state["power_required_W"],
        # Add design variables for convergence debugging
        "S_m2": state["S_m2"],
        "AR": state["AR"],
        "V_cruise_ms": state["V_cruise_ms"],
    }
    
    # We append the snapshot to history
    new_history = list(state.get("history", []))
    new_history.append(snapshot)

    logger.info("Constraints check: %d violations found.", len(violations))
    for v in violations:
        logger.info("  - Violation: %s (severity=%.2f)", v.parameter, v.severity)

    return {
        "violations": violations,
        "converged": converged,
        "history": new_history,
    }

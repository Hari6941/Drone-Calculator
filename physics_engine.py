"""
physics_engine.py

Pure aerodynamic/performance functions for the Fixed Wing UAV Design
Intelligence System. No I/O, no framework dependencies, NumPy only.

All units are SI:
    mass    -> kg
    length  -> m
    speed   -> m/s
    density -> kg/m^3
    force   -> N
    power   -> W

Frozen once validated (see AGENTS.md). Do not modify without review.
"""

import numpy as np

G = 9.80665  # standard gravity, m/s^2


def lift_coefficient_required(MTOW_kg: float, V_ms: float, rho: float, S_m2: float) -> float:
    """
    CL required for steady level flight.

    Source: Anderson, "Fundamentals of Aerodynamics", eq. 5.21
        L = W  =>  CL = 2*W / (rho * V^2 * S)

    Args:
        MTOW_kg: max takeoff weight, kg
        V_ms: cruise/flight speed, m/s
        rho: air density, kg/m^3
        S_m2: wing reference area, m^2

    Returns:
        CL (dimensionless)
    """
    if V_ms <= 0 or S_m2 <= 0 or rho <= 0:
        raise ValueError("V_ms, S_m2, and rho must be positive")
    W = MTOW_kg * G
    return (2 * W) / (rho * V_ms**2 * S_m2)


def stall_speed(MTOW_kg: float, rho: float, S_m2: float, CL_max: float) -> float:
    """
    Stall speed at 1g level flight.

    Source: Anderson, "Fundamentals of Aerodynamics", eq. 5.22 (rearranged)
        V_stall = sqrt(2*W / (rho * S * CL_max))

    Args:
        MTOW_kg: max takeoff weight, kg
        rho: air density, kg/m^3
        S_m2: wing reference area, m^2
        CL_max: maximum lift coefficient of the airfoil/wing

    Returns:
        V_stall, m/s
    """
    if S_m2 <= 0 or rho <= 0 or CL_max <= 0:
        raise ValueError("S_m2, rho, and CL_max must be positive")
    W = MTOW_kg * G
    return np.sqrt((2 * W) / (rho * S_m2 * CL_max))


def drag_polar(CL: float, CD0: float, AR: float, e: float) -> float:
    """
    Total drag coefficient from the classic parabolic drag polar.

    Source: Raymer, "Aircraft Design: A Conceptual Approach", eq. 12.5
        CD = CD0 + CL^2 / (pi * AR * e)

    Args:
        CL: lift coefficient
        CD0: zero-lift (parasite) drag coefficient
        AR: aspect ratio (span^2 / S)
        e: Oswald efficiency factor (typically 0.7-0.85 for small UAVs)

    Returns:
        CD_total (dimensionless)
    """
    if AR <= 0 or e <= 0:
        raise ValueError("AR and e must be positive")
    CD_induced = CL**2 / (np.pi * AR * e)
    return CD0 + CD_induced


def L_D_ratio(CL: float, CD: float) -> float:
    """
    Lift-to-drag ratio, the primary efficiency metric for cruise.

    Args:
        CL: lift coefficient
        CD: drag coefficient

    Returns:
        L/D (dimensionless)
    """
    if CD <= 0:
        raise ValueError("CD must be positive")
    return CL / CD


def power_required(drag_N: float, V_ms: float) -> float:
    """
    Power required to overcome drag at a given speed (thrust power,
    not accounting for propulsive/motor efficiency).

    Source: Anderson, "Fundamentals of Aerodynamics", eq. 6.24 (P = D*V)

    Args:
        drag_N: drag force, N
        V_ms: flight speed, m/s

    Returns:
        Power, W
    """
    if V_ms < 0:
        raise ValueError("V_ms must be non-negative")
    return drag_N * V_ms


def compute_design_point(inputs: dict) -> dict:
    """
    Runs the full chain of aero/performance equations for a single
    design point and returns the shared state dict fields defined
    in AGENTS.md.

    Required keys in `inputs`:
        MTOW_kg, V_cruise_ms, rho, S_m2, AR, e, CD0, CL_max

    Returns dict with keys:
        wing_area_m2, CL_cruise, CD_total, stall_speed_ms,
        L_D_ratio, power_required_W
    """
    required = ["MTOW_kg", "V_cruise_ms", "rho", "S_m2", "AR", "e", "CD0", "CL_max"]
    missing = [k for k in required if k not in inputs]
    if missing:
        raise ValueError(f"Missing required inputs: {missing}")

    MTOW_kg = inputs["MTOW_kg"]
    V_cruise_ms = inputs["V_cruise_ms"]
    rho = inputs["rho"]
    S_m2 = inputs["S_m2"]
    AR = inputs["AR"]
    e = inputs["e"]
    CD0 = inputs["CD0"]
    CL_max = inputs["CL_max"]

    CL_cruise = lift_coefficient_required(MTOW_kg, V_cruise_ms, rho, S_m2)
    CD_total = drag_polar(CL_cruise, CD0, AR, e)
    LD = L_D_ratio(CL_cruise, CD_total)
    V_stall = stall_speed(MTOW_kg, rho, S_m2, CL_max)

    W = MTOW_kg * G
    drag_N = W / LD  # since L/D = L/D and L = W in level flight
    P_req = power_required(drag_N, V_cruise_ms)

    return {
        "wing_area_m2": S_m2,
        "CL_cruise": CL_cruise,
        "CD_total": CD_total,
        "stall_speed_ms": V_stall,
        "L_D_ratio": LD,
        "power_required_W": P_req,
    }

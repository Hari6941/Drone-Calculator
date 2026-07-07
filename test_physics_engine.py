"""
test_physics_engine.py

Validation tests for physics_engine.py.

Test strategy:
1. Identity/sanity checks — things that must be true by definition,
   regardless of any external data (catches sign errors, unit bugs).
2. A published reference aircraft (Cessna 172) used as a rough
   real-world sanity check. These figures are approximate publicly
   known specs, not lab-precision truth — treat the 5% tolerance as
   "is this in the right ballpark", not "is this exact".

Run with: pytest test_physics_engine.py -v
"""

import numpy as np
import pytest
from physics_engine import (
    lift_coefficient_required,
    stall_speed,
    drag_polar,
    L_D_ratio,
    power_required,
    compute_design_point,
    G,
)


# ---------------------------------------------------------------------
# 1. Identity / sanity checks
# ---------------------------------------------------------------------

def test_lift_equals_weight_at_required_CL():
    """If we plug CL_required back into the lift equation, L must equal W."""
    MTOW_kg, V, rho, S = 1.5, 15.0, 1.225, 0.5
    CL = lift_coefficient_required(MTOW_kg, V, rho, S)
    L = 0.5 * rho * V**2 * S * CL
    W = MTOW_kg * G
    assert L == pytest.approx(W, rel=1e-6)


def test_stall_speed_matches_CL_max_lift_equation():
    """Plugging V_stall and CL_max back in should also satisfy L = W."""
    MTOW_kg, rho, S, CL_max = 1.5, 1.225, 0.5, 1.3
    V_stall = stall_speed(MTOW_kg, rho, S, CL_max)
    L = 0.5 * rho * V_stall**2 * S * CL_max
    W = MTOW_kg * G
    assert L == pytest.approx(W, rel=1e-6)


def test_drag_polar_minimum_at_zero_lift():
    """At CL = 0, CD_total should equal CD0 exactly (no induced drag)."""
    CD0 = 0.02
    CD = drag_polar(CL=0.0, CD0=CD0, AR=8.0, e=0.8)
    assert CD == pytest.approx(CD0, rel=1e-9)


def test_drag_polar_increases_with_CL():
    """Induced drag grows with CL^2, so higher CL must mean higher CD."""
    CD_low = drag_polar(CL=0.3, CD0=0.02, AR=8.0, e=0.8)
    CD_high = drag_polar(CL=0.9, CD0=0.02, AR=8.0, e=0.8)
    assert CD_high > CD_low


def test_L_D_ratio_basic():
    assert L_D_ratio(CL=0.6, CD=0.04) == pytest.approx(15.0)


def test_power_required_scales_linearly_with_speed():
    P1 = power_required(drag_N=10.0, V_ms=10.0)
    P2 = power_required(drag_N=10.0, V_ms=20.0)
    assert P2 == pytest.approx(2 * P1)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        lift_coefficient_required(MTOW_kg=1.0, V_ms=0, rho=1.225, S_m2=0.5)
    with pytest.raises(ValueError):
        stall_speed(MTOW_kg=1.0, rho=1.225, S_m2=0.5, CL_max=0)
    with pytest.raises(ValueError):
        drag_polar(CL=0.5, CD0=0.02, AR=0, e=0.8)


# ---------------------------------------------------------------------
# 2. Reference aircraft check — Cessna 172 (approximate published specs)
#    MTOW ~1111 kg, S ~16.2 m^2, AR ~7.32, cruise ~62 m/s at sea level,
#    CD0 ~0.031, e ~0.8, CL_max ~1.4 (flaps up)
#    Expected cruise L/D for a 172-class airframe: roughly 10-12
# ---------------------------------------------------------------------

def test_cessna172_cruise_CL_in_expected_range():
    inputs = {
        "MTOW_kg": 1111.0,
        "V_cruise_ms": 62.0,
        "rho": 1.225,
        "S_m2": 16.2,
        "AR": 7.32,
        "e": 0.8,
        "CD0": 0.031,
        "CL_max": 1.4,
    }
    result = compute_design_point(inputs)

    # Cruise CL for this class of aircraft is typically 0.25-0.45
    assert 0.2 < result["CL_cruise"] < 0.5

    # Published stall speed for the 172 (flaps up) is ~26-27 m/s (~50 kt)
    assert result["stall_speed_ms"] == pytest.approx(27.0, rel=0.15)

    # Cruise L/D for a 172-class airframe is roughly 10-12
    assert 8.0 < result["L_D_ratio"] < 14.0

    # Sanity: power required should be positive and in a plausible
    # range for a ~1100 kg airframe at cruise (order of tens of kW)
    assert 10_000 < result["power_required_W"] < 100_000


def test_compute_design_point_returns_all_required_keys():
    inputs = {
        "MTOW_kg": 1111.0,
        "V_cruise_ms": 62.0,
        "rho": 1.225,
        "S_m2": 16.2,
        "AR": 7.32,
        "e": 0.8,
        "CD0": 0.031,
        "CL_max": 1.4,
    }
    result = compute_design_point(inputs)
    expected_keys = {
        "wing_area_m2",
        "CL_cruise",
        "CD_total",
        "stall_speed_ms",
        "L_D_ratio",
        "power_required_W",
    }
    assert expected_keys == set(result.keys())


def test_compute_design_point_missing_input_raises():
    with pytest.raises(ValueError):
        compute_design_point({"MTOW_kg": 1.0})

"""
test_design_agent.py

Verification tests for the LangGraph UAV Design Agent.
"""

from pathlib import Path
import pytest
import numpy as np

from agents import run_design_agent, DEFAULT_CANDIDATES
from agents.state import Violation

def test_shared_keys_complete():
    """Verify that the agent returns all 10 AGENTS.md contract keys with correct types."""
    inputs = {
        "payload_kg": 1.0,
        "mtow_limit_kg": 3.0,
        "wingspan_limit_m": 1.5,
        "V_cruise_target_ms": 15.0,
        "candidate_airfoils": ["clarky", "n0012"],  # restrict to 2 to run fast
        "max_iterations": 3,
        "use_llm": False,
    }

    final_state = run_design_agent(inputs)

    # 10 keys required by AGENTS.md
    required_keys = [
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

    for key in required_keys:
        assert key in final_state, f"Missing contract key: {key}"

    # Verify types and positive values
    assert isinstance(final_state["airfoil_id"], str)
    assert final_state["airfoil_id"] in ["clarky", "n0012"]

    for key in required_keys:
        if key != "airfoil_id":
            val = final_state[key]
            assert isinstance(val, (float, int, np.floating, np.integer))
            assert val > 0.0, f"Value of {key} should be positive, got {val}"


def test_tight_constraints_best_effort():
    """Verify that the agent terminates gracefully with converged=False

    when constraints are impossible to satisfy, returning best-effort results.
    """
    inputs = {
        "payload_kg": 1.0,
        "mtow_limit_kg": 2.0,
        # Intentionally infeasible wingspan limit (0.3m) for a 2kg plane at 12 m/s
        "wingspan_limit_m": 0.3,
        "V_cruise_target_ms": 12.0,
        "power_limit_W": 20.0,  # very low power
        "candidate_airfoils": ["clarky"],
        "max_iterations": 4,
        "use_llm": False,
    }

    final_state = run_design_agent(inputs)

    # Must terminate gracefully, marking converged as False
    assert final_state["converged"] is False
    assert final_state["iteration"] >= 4
    assert len(final_state["violations"]) > 0
    
    # Check that wingspan limit is violated in final state (since 0.3m is impossible)
    span_violation = next((v for v in final_state["violations"] if v.parameter == "span_m"), None)
    assert span_violation is not None
    assert span_violation.actual > 0.3


def test_cessna_like_converges():
    """Verify that a feasible design space converges successfully in a few iterations."""
    inputs = {
        "payload_kg": 1.5,
        "mtow_limit_kg": 4.5,
        "wingspan_limit_m": 1.8,
        "V_cruise_target_ms": 16.0,
        "stall_speed_limit_ms": 11.0,
        "power_limit_W": 250.0,
        "candidate_airfoils": ["clarky", "n0012"],
        "max_iterations": 10,
        "use_llm": False,
    }

    final_state = run_design_agent(inputs)

    # Must converge successfully
    assert final_state["converged"] is True
    assert final_state["iteration"] < 10
    assert len(final_state["violations"]) == 0

    # Verify constraints are satisfied
    assert final_state["span_m"] <= 1.8
    assert final_state["stall_speed_ms"] <= 11.0
    assert final_state["power_required_W"] <= 250.0
    assert final_state["MTOW_kg"] <= 4.5
    assert final_state["CL_cruise"] < 0.8 * final_state["CL_max"]

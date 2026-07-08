"""
state.py

State schema, competition rules, and violation definitions for the LangGraph design agent.
All units are SI.
"""

from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass

DEFAULT_CANDIDATES = [
    "clarky",
    "n0012",
    "s1223",
    "e387",
    "sd7037",
    "ag03",
    "dae11",
    "n2412",
    "s7055"
]

@dataclass(frozen=True)
class CompetitionRules:
    """Competition rules/constraints. All units are SI."""
    payload_kg: float
    mtow_limit_kg: float
    wingspan_limit_m: float
    V_cruise_target_ms: float
    power_limit_W: Optional[float] = None
    stall_speed_limit_ms: Optional[float] = None
    rho: float = 1.225

@dataclass
class Violation:
    """A constraint violation descriptor."""
    parameter: str
    limit: float
    actual: float
    severity: float  # (actual - limit) / limit for upper limits, (limit - actual) / limit for lower limits
    suggestion: str

class DesignState(TypedDict, total=False):
    # Inputs (passed by user at startup)
    payload_kg: float
    mtow_limit_kg: float
    wingspan_limit_m: float
    V_cruise_target_ms: float
    power_limit_W: float
    stall_speed_limit_ms: float
    rho: float

    # AGENTS.md Shared Keys (output contract)
    wing_area_m2: float
    aspect_ratio: float
    airfoil_id: str
    CL_cruise: float
    CD_total: float
    MTOW_kg: float
    stall_speed_ms: float
    L_D_ratio: float
    span_m: float
    power_required_W: float

    # Design variables (adjustable knobs)
    V_cruise_ms: float
    S_m2: float
    AR: float
    e: float
    CD0: float
    CL_max: float
    Re: float

    # Orchestration metadata
    rules: CompetitionRules
    iteration: int
    max_iterations: int
    converged: bool
    violations: List[Violation]
    history: List[Dict[str, Any]]
    candidate_airfoils: List[str]
    reasoning: str
    use_llm: bool

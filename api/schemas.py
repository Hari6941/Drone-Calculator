"""
schemas.py

Pydantic v2 schemas representing request and response shapes defined in api_contract.md.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class CompetitionRulesRequest(BaseModel):
    MTOW_kg: float = Field(..., gt=0, description="Max Takeoff Weight, kg")
    payload_kg: float = Field(..., gt=0, description="Payload Weight, kg")
    max_wingspan_m: float = Field(..., gt=0, description="Max Wingspan, m")
    KV_rating: Optional[int] = Field(None, gt=0, description="Motor KV rating")
    max_power_W: Optional[float] = Field(None, gt=0, description="Max motor power limit, W")
    min_stall_speed_ms: Optional[float] = Field(None, gt=0, description="Max allowable stall speed, m/s")
    target_cruise_speed_ms: float = Field(15.0, gt=0, description="Target cruise speed, m/s (default 15.0)")
    custom_airfoil_paths: List[str] = Field(default_factory=list, description="Filesystem paths to user airfoil .dat files")

class DesignRequest(BaseModel):
    competition_rules: CompetitionRulesRequest
    use_llm: bool = Field(default=False, description="Whether to trigger Claude-based design adjustments")
    max_iterations: int = Field(default=10, gt=0, description="Max design optimization iterations")


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class DesignKeys(BaseModel):
    """Exactly the 10 AGENTS.md shared keys."""
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

class DesignVariables(BaseModel):
    """The 7 design variables from Phase 3 agent."""
    V_cruise_ms: float
    S_m2: float
    AR: float
    e: float
    CD0: float
    CL_max: float
    Re: float

class ViolationResponse(BaseModel):
    """Violation schema matching Phase 3 state and API contract."""
    parameter: str
    limit: float
    actual: float
    severity: Union[float, str]
    suggestion: str

class HistoryEntry(BaseModel):
    """Snapshot at a specific design iteration."""
    iteration: int
    design_variables: DesignVariables
    violations: List[ViolationResponse]
    reasoning: str

class DesignResponse(BaseModel):
    """Full optimization run result matching api_contract.md response shape."""
    id: str = Field(..., description="Unique UUID for this design run")
    created_at: str = Field(..., description="Timestamp of when the design was generated")
    status: str = Field(..., description="'converged' | 'best_effort' | 'no_viable_airfoil'")
    iterations_used: int
    converged: bool
    design: DesignKeys
    design_variables: DesignVariables
    violations: List[ViolationResponse]
    history: List[HistoryEntry]
    candidate_airfoils_considered: List[str]
    airfoil_selection_reasoning: str

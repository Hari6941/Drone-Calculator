"""
graph.py

StateGraph definition and compilation for the design convergence agent.
"""

import logging
from langgraph.graph import StateGraph, START, END

from agents.state import DesignState
from agents.nodes.ingest_rules import ingest_rules
from agents.nodes.seed_design import seed_design
from agents.nodes.evaluate_aero import evaluate_aero
from agents.nodes.select_airfoil import select_airfoil
from agents.nodes.check_constraints import check_constraints
from agents.nodes.adjust_design import adjust_design
from agents.nodes.finalize_design import finalize_design

logger = logging.getLogger(__name__)

def route_after_check(state: DesignState) -> str:
    """Conditional routing after checking constraints.
    Goes to finalize_design if converged or max iterations reached,
    otherwise goes to adjust_design.
    """
    if state["converged"]:
        logger.info("Design has converged! Routing to finalize.")
        return "finalize_design"
    
    if state["iteration"] >= state["max_iterations"]:
        logger.warning(
            "Max iterations (%d/%d) reached without convergence. Routing to finalize.",
            state["iteration"], state["max_iterations"]
        )
        return "finalize_design"
        
    logger.info(
        "Design not converged (iteration %d/%d). Routing to adjust.",
        state["iteration"], state["max_iterations"]
    )
    return "adjust_design"

def build_graph() -> StateGraph:
    """Constructs and returns the StateGraph for the design agent."""
    workflow = StateGraph(DesignState)

    # Add all nodes
    workflow.add_node("ingest_rules", ingest_rules)
    workflow.add_node("seed_design", seed_design)
    workflow.add_node("evaluate_aero", evaluate_aero)
    workflow.add_node("select_airfoil", select_airfoil)
    workflow.add_node("check_constraints", check_constraints)
    workflow.add_node("adjust_design", adjust_design)
    workflow.add_node("finalize_design", finalize_design)

    # Wire the flow
    workflow.add_edge(START, "ingest_rules")
    workflow.add_edge("ingest_rules", "seed_design")
    workflow.add_edge("seed_design", "evaluate_aero")
    workflow.add_edge("evaluate_aero", "select_airfoil")
    workflow.add_edge("select_airfoil", "check_constraints")
    
    # Conditional routing from constraints check
    workflow.add_conditional_edges(
        "check_constraints",
        route_after_check,
        {
            "finalize_design": "finalize_design",
            "adjust_design": "adjust_design",
        }
    )
    
    # Loop back from adjust to evaluate
    workflow.add_edge("adjust_design", "evaluate_aero")
    workflow.add_edge("finalize_design", END)

    return workflow

def run_design_agent(inputs: dict) -> dict:
    """Compiles and runs the design agent with the given inputs.

    Required keys in `inputs`:
        payload_kg: float
        mtow_limit_kg: float
        wingspan_limit_m: float
        V_cruise_target_ms: float

    Optional keys:
        power_limit_W: float
        stall_speed_limit_ms: float
        rho: float (default 1.225)
        candidate_airfoils: List[str]
        max_iterations: int (default 10)
        use_llm: bool (default False)

    Returns:
        The final DesignState dictionary.
    """
    workflow = build_graph()
    app = workflow.compile()
    
    # Run the graph
    final_state = app.invoke(inputs)
    return final_state

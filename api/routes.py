"""
routes.py

FastAPI route handlers for design optimization and design history endpoints.
"""

import asyncio
import datetime
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from api.database import get_design_by_id, get_design_history, save_design
from api.schemas import DesignRequest, DesignResponse
from agents import run_design_agent, build_graph, DEFAULT_CANDIDATES
from airfoil_engine.uiuc_parser import validate_dat_file, parse_dat_file
from physics_engine import G

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

_design_lock = asyncio.Lock()

# Helper to inspect why a dat file failed validation
def _get_dat_validation_error_reason(path: Path) -> str:
    if not path.exists():
        return "file does not exist"
    try:
        # Re-run parser steps to find the exact check that fails
        geom = parse_dat_file(path)
        coords = geom.coordinates
        count = len(coords)
        if count < 8 or count > 500:
            return f"coordinate count {count} is out of sane range [8, 500]"
        
        x = coords[:, 0]
        y = coords[:, 1]
        
        import numpy as np
        chord = float(np.max(x) - np.min(x))
        if not (0.95 <= chord <= 1.05):
            return f"chord length {chord:.4f} is not close to 1.0"
            
        if np.any((x < -0.05) | (x > 1.05)):
            return "some x coordinates are out of bounds [-0.05, 1.05]"
            
        if np.any((y < -0.5) | (y > 0.5)):
            return "some y coordinates are out of bounds [-0.5, 0.5]"
            
        return "unknown validation failure"
    except Exception as exc:
        return f"format parse error: {str(exc)}"


def _build_design_response(
    final_state: dict,
    rules_req: Any,
    inputs: dict,
    reasoning_by_iter: Dict[int, str],
    airfoil_cl_max: Dict[str, float],
    airfoil_cd0: Dict[str, float],
) -> dict:
    """Helper to map final state to the contract-compliant response shape."""
    # 4. Map final state to the contract-compliant response shape
    converged = final_state.get("converged", False)
    iterations_used = final_state.get("iteration", 0)

    # Determine status
    if converged:
        status_str = "converged"
    else:
        # Check if CL_margin or CL_cruise is violated
        violations = final_state.get("violations", [])
        has_airfoil_fail = any(v.parameter in ("CL_margin", "CL_cruise") for v in violations)
        status_str = "no_viable_airfoil" if has_airfoil_fail else "best_effort"

    # Map the 10 AGENTS.md shared keys
    design = {
        "wing_area_m2": final_state.get("wing_area_m2", 0.0),
        "aspect_ratio": final_state.get("aspect_ratio", 0.0),
        "airfoil_id": final_state.get("airfoil_id", "clarky"),
        "CL_cruise": final_state.get("CL_cruise", 0.0),
        "CD_total": final_state.get("CD_total", 0.0),
        "MTOW_kg": final_state.get("MTOW_kg", 0.0),
        "stall_speed_ms": final_state.get("stall_speed_ms", 0.0),
        "L_D_ratio": final_state.get("L_D_ratio", 0.0),
        "span_m": final_state.get("span_m", 0.0),
        "power_required_W": final_state.get("power_required_W", 0.0),
    }

    # Map the 7 design variables
    design_variables = {
        "V_cruise_ms": final_state.get("V_cruise_ms", 0.0),
        "S_m2": final_state.get("S_m2", 0.0),
        "AR": final_state.get("AR", 0.0),
        "e": final_state.get("e", 0.80),
        "CD0": final_state.get("CD0", 0.025),
        "CL_max": final_state.get("CL_max", 1.2),
        "Re": final_state.get("Re", 200000.0),
    }

    # Map current violations
    api_violations = [
        {
            "parameter": v.parameter,
            "limit": v.limit,
            "actual": v.actual,
            "severity": v.severity,
            "suggestion": v.suggestion,
        }
        for v in final_state.get("violations", [])
    ]

    # Reconstruct history mapping
    history_entries = []
    agent_history = final_state.get("history", [])
    
    import numpy as np

    for idx, snap in enumerate(agent_history):
        snap_airfoil = snap["airfoil_id"]
        snap_cl_max = airfoil_cl_max.get(snap_airfoil, 1.2)
        snap_cd0 = airfoil_cd0.get(snap_airfoil, 0.025)
        
        # Calculate Re
        rho = 1.225
        span = snap["span_m"]
        S_m2 = snap["S_m2"]
        V_cruise = snap["V_cruise_ms"]
        chord = S_m2 / span if span > 0 else 0.1
        snap_Re = (rho * V_cruise * chord) / 1.789e-5

        snap_vars = {
            "V_cruise_ms": V_cruise,
            "S_m2": S_m2,
            "AR": snap["AR"],
            "e": final_state.get("e", 0.80),
            "CD0": snap_cd0,
            "CL_max": snap_cl_max,
            "Re": snap_Re,
        }

        # Calculate violations for this snapshot
        snap_violations = []
        if span > rules_req.max_wingspan_m:
            snap_violations.append({
                "parameter": "span_m",
                "limit": rules_req.max_wingspan_m,
                "actual": span,
                "severity": (span - rules_req.max_wingspan_m) / rules_req.max_wingspan_m,
                "suggestion": f"Wingspan {span:.3f} m exceeds limit {rules_req.max_wingspan_m:.2f} m.",
            })
            
        stall_speed = snap["stall_speed_ms"]
        if rules_req.min_stall_speed_ms is not None:
            if stall_speed > rules_req.min_stall_speed_ms:
                snap_violations.append({
                    "parameter": "stall_speed_ms",
                    "limit": rules_req.min_stall_speed_ms,
                    "actual": stall_speed,
                    "severity": (stall_speed - rules_req.min_stall_speed_ms) / rules_req.min_stall_speed_ms,
                    "suggestion": f"Stall speed {stall_speed:.2f} m/s exceeds limit {rules_req.min_stall_speed_ms:.2f} m/s.",
                })

        power = snap["power_required_W"]
        if rules_req.max_power_W is not None:
            if power > rules_req.max_power_W:
                snap_violations.append({
                    "parameter": "power_required_W",
                    "limit": rules_req.max_power_W,
                    "actual": power,
                    "severity": (power - rules_req.max_power_W) / rules_req.max_power_W,
                    "suggestion": f"Power required {power:.1f} W exceeds limit {rules_req.max_power_W:.1f} W.",
                })

        cl_cruise = snap["CL_cruise"]
        cl_limit = 0.8 * snap_cl_max
        if cl_cruise > cl_limit:
            snap_violations.append({
                "parameter": "CL_cruise",
                "limit": cl_limit,
                "actual": cl_cruise,
                "severity": (cl_cruise - cl_limit) / cl_limit,
                "suggestion": f"Cruise CL {cl_cruise:.3f} exceeds safety limit {cl_limit:.3f}.",
            })

        margin = snap_cl_max - cl_cruise
        if margin < 0.3:
            snap_violations.append({
                "parameter": "CL_margin",
                "limit": 0.3,
                "actual": margin,
                "severity": (0.3 - margin) / 0.3,
                "suggestion": f"Airfoil CL margin {margin:.3f} is below 0.3.",
            })

        # Match reasoning: step 0 has initialization, step i has reasoning from adjust_design i
        snap_reasoning = "Initialization completed." if idx == 0 else reasoning_by_iter.get(idx, "Adjusting parameters.")

        history_entries.append({
            "iteration": idx + 1,
            "design_variables": snap_vars,
            "violations": snap_violations,
            "reasoning": snap_reasoning,
        })

    # Prepare response envelope
    design_id = str(uuid.uuid4())
    created_at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "") + "Z"
    
    airfoil_id = design["airfoil_id"]
    airfoil_selection_reasoning = f"{airfoil_id} selected: optimal L/D ratio and lift margin at target Re."

    response_payload = {
        "id": design_id,
        "created_at": created_at,
        "status": status_str,
        "iterations_used": iterations_used,
        "converged": converged,
        "design": design,
        "design_variables": design_variables,
        "violations": api_violations,
        "history": history_entries,
        "candidate_airfoils_considered": inputs["candidate_airfoils"],
        "airfoil_selection_reasoning": airfoil_selection_reasoning,
    }

    return response_payload


def _run_design_optimization_sync(request: DesignRequest) -> Dict[str, Any]:
    """Synchronous helper function containing the core design agent workflow execution and DB saving."""
    rules_req = request.competition_rules
    project_root = Path(__file__).resolve().parent.parent
    
    # 1. Validate custom dat files if supplied
    for path_str in rules_req.custom_airfoil_paths:
        path = Path(path_str)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        else:
            path = path.resolve()
            
        # Call validate_dat_file exactly as requested
        if not validate_dat_file(path):
            reason = _get_dat_validation_error_reason(path)
            logger.warning("Custom dat file %s failed validation: %s", path_str, reason)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "Custom airfoil .dat file validation failed",
                    "file": path_str,
                    "reason": reason,
                },
            )

    # 2. Prepare inputs for the Phase 3 LangGraph design agent
    inputs = {
        "payload_kg": rules_req.payload_kg,
        "mtow_limit_kg": rules_req.MTOW_kg,
        "wingspan_limit_m": rules_req.max_wingspan_m,
        "power_limit_W": rules_req.max_power_W,
        "stall_speed_limit_ms": rules_req.min_stall_speed_ms,
        "V_cruise_target_ms": rules_req.target_cruise_speed_ms,
        "candidate_airfoils": list(DEFAULT_CANDIDATES) + rules_req.custom_airfoil_paths,
        "max_iterations": request.max_iterations,
        "use_llm": request.use_llm,
    }

    # 3. Stream graph execution to capture iteration-by-iteration reasoning and design variables
    workflow = build_graph()
    app = workflow.compile()

    final_state = {}
    reasoning_by_iter: Dict[int, str] = {}
    airfoil_cl_max: Dict[str, float] = {"clarky": 1.393, "n0012": 1.085} # seed defaults
    airfoil_cd0: Dict[str, float] = {"clarky": 0.0102, "n0012": 0.0114}

    try:
        for chunk in app.stream(inputs):
            for node_name, state_update in chunk.items():
                final_state.update(state_update)
                
                # Capture airfoil metadata when evaluated
                if node_name == "select_airfoil":
                    airfoil_id = state_update.get("airfoil_id")
                    if airfoil_id:
                        if "CL_max" in state_update:
                            airfoil_cl_max[airfoil_id] = state_update["CL_max"]
                        if "CD0" in state_update:
                            airfoil_cd0[airfoil_id] = state_update["CD0"]

                # Capture reasoning for adjustments
                if node_name == "adjust_design":
                    iter_num = state_update.get("iteration")
                    reasoning = state_update.get("reasoning", "")
                    reasoning_by_iter[iter_num] = reasoning

    except Exception as exc:
        logger.error("Design agent execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unhandled backend optimization error: {str(exc)}",
        )

    # 4. Map final state to the contract-compliant response shape using helper
    response_payload = _build_design_response(
        final_state=final_state,
        rules_req=rules_req,
        inputs=inputs,
        reasoning_by_iter=reasoning_by_iter,
        airfoil_cl_max=airfoil_cl_max,
        airfoil_cd0=airfoil_cd0
    )

    # 5. Persist design to SQLite database
    try:
        save_design(
            design_id=response_payload["id"],
            created_at=response_payload["created_at"],
            payload_kg=rules_req.payload_kg,
            mtow_limit_kg=rules_req.MTOW_kg,
            wingspan_limit_m=rules_req.max_wingspan_m,
            status=response_payload["status"],
            converged=response_payload["converged"],
            response_json=json.dumps(response_payload),
        )
    except Exception as exc:
        logger.error("Failed to save design %s to SQLite: %s", response_payload["id"], exc)

    return response_payload


@router.post(
    "/design",
    response_model=DesignResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize a new UAV design from competition rules",
)
async def create_design(request: DesignRequest):
    """Triggers the LangGraph optimization agent to converge on a design spec
    satisfying the given competition constraints.
    """
    rules_req = request.competition_rules
    
    # 1. Path whitelist validation (reject any path containing ".." or resolving outside data/user_airfoils/)
    project_root = Path(__file__).resolve().parent.parent
    whitelist_dir = (project_root / "data" / "user_airfoils").resolve()
    
    for path_str in rules_req.custom_airfoil_paths:
        if ".." in path_str:
            logger.warning("Custom dat file path %s contains '..'", path_str)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access denied for airfoil path: path must not contain '..'",
            )
        
        path = Path(path_str)
        if not path.is_absolute():
            resolved_path = (project_root / path).resolve()
        else:
            resolved_path = path.resolve()
            
        if not resolved_path.is_relative_to(whitelist_dir):
            logger.warning("Custom dat file path %s resolves outside %s", path_str, whitelist_dir)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access denied for airfoil path: path must be under data/user_airfoils/ directory",
            )

    # 2. Concurrency lock
    if _design_lock.locked():
        logger.warning("Rejecting concurrent design request: lock is already held")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Another design optimization run is currently in progress.",
        )

    async with _design_lock:
        return await asyncio.to_thread(_run_design_optimization_sync, request)


import queue
import threading

@router.post(
    "/design/stream",
    summary="Optimize a new UAV design and stream node-by-node execution progress",
)
async def create_design_stream(request: DesignRequest):
    """Triggers the LangGraph optimization agent and returns a StreamingResponse
    yielding Server-Sent Events (SSE) detailing node-by-node execution progress.
    """
    rules_req = request.competition_rules
    
    # 1. Path whitelist validation (reject any path containing ".." or resolving outside data/user_airfoils/)
    project_root = Path(__file__).resolve().parent.parent
    whitelist_dir = (project_root / "data" / "user_airfoils").resolve()
    
    for path_str in rules_req.custom_airfoil_paths:
        if ".." in path_str:
            logger.warning("Custom dat file path %s contains '..'", path_str)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access denied for airfoil path: path must not contain '..'",
            )
        
        path = Path(path_str)
        if not path.is_absolute():
            resolved_path = (project_root / path).resolve()
        else:
            resolved_path = path.resolve()
            
        if not resolved_path.is_relative_to(whitelist_dir):
            logger.warning("Custom dat file path %s resolves outside %s", path_str, whitelist_dir)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access denied for airfoil path: path must be under data/user_airfoils/ directory",
            )

    # 2. Concurrency lock
    if _design_lock.locked():
        logger.warning("Rejecting concurrent design request: lock is already held")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Another design optimization run is currently in progress.",
        )

    # Prepare inputs for the LangGraph design agent
    inputs = {
        "payload_kg": rules_req.payload_kg,
        "mtow_limit_kg": rules_req.MTOW_kg,
        "wingspan_limit_m": rules_req.max_wingspan_m,
        "power_limit_W": rules_req.max_power_W,
        "stall_speed_limit_ms": rules_req.min_stall_speed_ms,
        "V_cruise_target_ms": rules_req.target_cruise_speed_ms,
        "candidate_airfoils": list(DEFAULT_CANDIDATES) + rules_req.custom_airfoil_paths,
        "max_iterations": request.max_iterations,
        "use_llm": request.use_llm,
    }

    # Thread-safe queue and event callback
    event_queue = queue.Queue()
    airfoil_events = []
    
    def progress_callback(airfoil_id: str, status_str: str, details: dict):
        airfoil_events.append({
            "type": "airfoil_progress",
            "airfoil_id": airfoil_id,
            "status": status_str,
            "details": details
        })

    inputs["progress_callback"] = progress_callback

    def run_optimization_in_thread():
        try:
            workflow = build_graph()
            app = workflow.compile()

            final_state = {}
            reasoning_by_iter = {}
            airfoil_cl_max = {"clarky": 1.393, "n0012": 1.085} # seed defaults
            airfoil_cd0 = {"clarky": 0.0102, "n0012": 0.0114}

            event_queue.put({"type": "status", "message": "Starting UAV Design Optimization..."})

            next_node = "ingest_rules"
            event_queue.put({"type": "node_start", "node": next_node})

            for chunk in app.stream(inputs):
                for node_name, state_update in chunk.items():
                    final_state.update(state_update)

                    if node_name == "select_airfoil":
                        airfoil_id = state_update.get("airfoil_id")
                        if airfoil_id:
                            if "CL_max" in state_update:
                                airfoil_cl_max[airfoil_id] = state_update["CL_max"]
                            if "CD0" in state_update:
                                airfoil_cd0[airfoil_id] = state_update["CD0"]

                    if node_name == "adjust_design":
                        iter_num = state_update.get("iteration")
                        reasoning = state_update.get("reasoning", "")
                        reasoning_by_iter[iter_num] = reasoning

                    # Drain any accumulated airfoil progress events
                    while airfoil_events:
                        evt = airfoil_events.pop(0)
                        event_queue.put(evt)

                    # Yield node completion event
                    variables = {
                        "MTOW_kg": final_state.get("MTOW_kg"),
                        "span_m": final_state.get("span_m"),
                        "wing_area_m2": final_state.get("wing_area_m2"),
                        "V_cruise_ms": final_state.get("V_cruise_ms"),
                        "CL_cruise": final_state.get("CL_cruise"),
                        "CD_total": final_state.get("CD_total"),
                        "power_required_W": final_state.get("power_required_W"),
                        "stall_speed_ms": final_state.get("stall_speed_ms"),
                        "airfoil_id": final_state.get("airfoil_id"),
                        "converged": final_state.get("converged", False),
                    }
                    variables = {k: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v for k, v in variables.items()}

                    event_queue.put({
                        "type": "node_complete",
                        "node": node_name,
                        "iteration": int(final_state.get("iteration", 0)),
                        "variables": variables
                    })

                    # Map next node
                    if node_name == "ingest_rules":
                        next_node = "seed_design"
                    elif node_name == "seed_design":
                        next_node = "evaluate_aero"
                    elif node_name == "evaluate_aero":
                        next_node = "select_airfoil"
                    elif node_name == "select_airfoil":
                        next_node = "check_constraints"
                    elif node_name == "check_constraints":
                        if final_state.get("converged") or final_state.get("iteration", 0) >= final_state.get("max_iterations", 10):
                            next_node = "finalize_design"
                        else:
                            next_node = "adjust_design"
                    elif node_name == "adjust_design":
                        next_node = "evaluate_aero"
                    elif node_name == "finalize_design":
                        next_node = None

                    if next_node:
                        event_queue.put({"type": "node_start", "node": next_node})

            # Optimization complete, map response payload
            response_payload = _build_design_response(
                final_state=final_state,
                rules_req=rules_req,
                inputs=inputs,
                reasoning_by_iter=reasoning_by_iter,
                airfoil_cl_max=airfoil_cl_max,
                airfoil_cd0=airfoil_cd0
            )

            event_queue.put({"type": "complete", "result": response_payload})

        except Exception as exc:
            logger.error("Design stream execution failed: %s", exc, exc_info=True)
            event_queue.put({"type": "error", "detail": str(exc)})
        finally:
            event_queue.put(None)

    async def event_generator():
        async with _design_lock:
            thread = threading.Thread(target=run_optimization_in_thread)
            thread.start()

            loop = asyncio.get_running_loop()
            while True:
                evt = await loop.run_in_executor(None, event_queue.get)
                if evt is None:
                    break
                yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get(
    "/design/history",
    response_model=List[DesignResponse],
    summary="Get recent design optimization runs",
)
def get_history(limit: int = Query(20, ge=1, le=100)):
    """Retrieves recent design optimization runs from the SQLite database."""
    history = get_design_history(limit=limit)
    return history


@router.get(
    "/design/{design_id}",
    response_model=DesignResponse,
    summary="Get a previously computed design spec by ID",
)
def get_design(design_id: str):
    """Retrieves a historically saved design optimization run from SQLite by UUID."""
    design = get_design_by_id(design_id)
    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Design run with ID {design_id} not found",
        )
    return design


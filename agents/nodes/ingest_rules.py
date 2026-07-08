"""
ingest_rules.py

Node to parse and validate competition rules, process custom .dat files,
and initialize design state.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import List

from agents.state import DesignState, CompetitionRules, DEFAULT_CANDIDATES
from airfoil_engine.uiuc_parser import validate_dat_file, _DEFAULT_CACHE_DIR

logger = logging.getLogger(__name__)

def ingest_rules(state: DesignState) -> dict:
    """Parses and validates competition rules, handles custom .dat files,
    and initializes tracking variables.
    """
    logger.info("Ingesting competition rules and candidates...")

    # Extract rules inputs (raise if missing required fields)
    required = ["payload_kg", "mtow_limit_kg", "wingspan_limit_m", "V_cruise_target_ms"]
    missing = [r for r in required if r not in state]
    if missing:
        raise ValueError(f"Missing required competition rules: {missing}")

    rules = CompetitionRules(
        payload_kg=float(state["payload_kg"]),
        mtow_limit_kg=float(state["mtow_limit_kg"]),
        wingspan_limit_m=float(state["wingspan_limit_m"]),
        power_limit_W=state.get("power_limit_W"),
        stall_speed_limit_ms=state.get("stall_speed_limit_ms"),
        V_cruise_target_ms=float(state["V_cruise_target_ms"]),
        rho=float(state.get("rho", 1.225)),
    )

    # Process candidate airfoils
    user_candidates = state.get("candidate_airfoils")
    if not user_candidates:
        user_candidates = list(DEFAULT_CANDIDATES)

    processed_candidates: List[str] = []
    
    # Ensure cache directory exists
    cache_dir = Path(_DEFAULT_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    for item in user_candidates:
        path_check = Path(item)
        # Check if it looks like a path (has slash/dot/exists) or is a path
        if path_check.suffix.lower() == ".dat" or os.path.exists(item):
            if validate_dat_file(path_check):
                airfoil_id = path_check.stem.lower().replace(" ", "_")
                dest_path = cache_dir / f"{airfoil_id}.dat"
                try:
                    # Copy to cache directory so airfoil_engine can access it
                    shutil.copy2(path_check, dest_path)
                    logger.info("Copied and registered custom airfoil: %s -> %s", path_check, dest_path)
                    processed_candidates.append(airfoil_id)
                except Exception as exc:
                    logger.warning("Failed to copy custom airfoil %s: %s", item, exc)
            else:
                logger.warning("Skipping invalid custom airfoil .dat file: %s", item)
        else:
            # Standard UIUC airfoil ID
            processed_candidates.append(item.lower())

    if not processed_candidates:
        logger.warning("No valid candidate airfoils left! Falling back to default list.")
        processed_candidates = list(DEFAULT_CANDIDATES)

    # State initialization
    return {
        "rules": rules,
        "candidate_airfoils": processed_candidates,
        "MTOW_kg": rules.mtow_limit_kg,  # Set initial MTOW to the limit per AGENTS.md contract
        "iteration": 0,
        "max_iterations": state.get("max_iterations", 10),
        "converged": False,
        "violations": [],
        "history": [],
        "reasoning": "Initialization completed.",
        "use_llm": state.get("use_llm", False),
    }

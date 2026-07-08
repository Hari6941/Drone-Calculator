"""
adjust_design.py

Node to adjust design variables (S_m2, AR, V_cruise_ms) based on constraint violations.
Supports both deterministic rule-based adjustment and Claude-based LLM adjustment.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

from agents.state import DesignState, Violation

logger = logging.getLogger(__name__)

def _adjust_deterministic(state: DesignState) -> dict:
    """Fallback rule-based designer. Adjusts variables using proportional controls
    with iteration-based damping to guarantee convergence.
    """
    logger.info("Applying deterministic adjustment rules...")
    
    iteration = state["iteration"]
    S_m2 = state["S_m2"]
    AR = state["AR"]
    V_cruise_ms = state["V_cruise_ms"]
    rules = state["rules"]
    
    # Damping factor: decreases step size as iterations proceed to prevent oscillation
    damping = 1.0 / (1.0 + 0.4 * iteration)
    
    # We examine each violation and accumulate adjustment directions
    # S_m2_change, AR_change, V_change can be positive or negative
    S_m2_factor = 1.0
    AR_factor = 1.0
    V_factor = 1.0
    
    has_span = False
    has_stall = False
    has_power = False
    has_cl = False

    for v in state["violations"]:
        if v.parameter == "span_m":
            has_span = True
        elif v.parameter == "stall_speed_ms":
            has_stall = True
        elif v.parameter == "power_required_W":
            has_power = True
        elif v.parameter in ("CL_cruise", "CL_margin"):
            has_cl = True

    # 1. Handle wingspan (too long -> must reduce span -> reduce AR and/or S_m2)
    if has_span:
        # Reduce AR first, then S_m2
        AR_factor *= (1.0 - 0.12 * damping)
        if AR * AR_factor < 3.0:
            S_m2_factor *= (1.0 - 0.08 * damping)

    # 2. Handle stall speed (too fast -> must increase S_m2)
    if has_stall:
        S_m2_factor *= (1.0 + 0.15 * damping)

    # 3. Handle power required (too high -> reduce speed, S_m2, or increase AR)
    if has_power:
        V_factor *= (1.0 - 0.08 * damping)
        # If we also have a span violation, we can't increase AR, but if not:
        if not has_span:
            AR_factor *= (1.0 + 0.08 * damping)
        else:
            S_m2_factor *= (1.0 - 0.05 * damping)

    # 4. Handle CL cruise / margin (too high -> increase S_m2 or speed)
    if has_cl and not has_stall: # stall check already handles S_m2 increase
        if not has_span:
            S_m2_factor *= (1.0 + 0.10 * damping)
        else:
            V_factor *= (1.0 + 0.05 * damping)

    # Resolve conflicting constraints (e.g. span vs stall)
    # If we have both, we need to balance them.
    # The multiplicative accumulation does this naturally.

    # Apply adjustments
    S_m2 = S_m2 * S_m2_factor
    AR = AR * AR_factor
    V_cruise_ms = V_cruise_ms * V_factor

    # Apply hard physical constraints/bounds
    S_m2 = max(0.04, min(S_m2, 10.0))
    AR = max(3.0, min(AR, 12.0))
    
    # Speed bounds: keep V_cruise_ms above stall speed with a safety factor,
    # but not too slow or too fast.
    min_speed = state.get("stall_speed_ms", 10.0) * 1.15
    V_cruise_ms = max(min_speed, min(V_cruise_ms, rules.V_cruise_target_ms * 1.5))

    reasoning = (
        f"Deterministic adjustment (iteration {iteration}): "
        f"S_m2={S_m2:.4f} (changed by {S_m2_factor-1.0:+.1%}), "
        f"AR={AR:.2f} (changed by {AR_factor-1.0:+.1%}), "
        f"V_cruise_ms={V_cruise_ms:.2f} (changed by {V_factor-1.0:+.1%})."
    )
    
    logger.info("Deterministic Adjustment: %s", reasoning)
    
    return {
        "S_m2": S_m2,
        "AR": AR,
        "V_cruise_ms": V_cruise_ms,
        "reasoning": reasoning,
        "iteration": iteration + 1,
    }

def _adjust_llm(state: DesignState) -> dict:
    """Claude-powered designer. Instructs Claude to review violations and history,
    then output adjusted variables in JSON format.
    """
    logger.info("Applying LLM-based adjustment...")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not found in environment. Falling back to deterministic adjustment.")
        return _adjust_deterministic(state)

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic module not installed. Falling back to deterministic adjustment.")
        return _adjust_deterministic(state)

    # Load prompt template
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "adjust_design.md"
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
    else:
        system_prompt = "You are a senior UAV aerodynamic design assistant."

    # Format current state context
    history_summary = []
    for idx, snap in enumerate(state.get("history", [])):
        history_summary.append(
            f"Iter {idx}: S_m2={snap['S_m2']:.3f}, AR={snap['aspect_ratio']:.1f}, "
            f"V_cruise={snap.get('V_cruise_ms', 0.0):.1f}, span={snap['span_m']:.2f}, "
            f"power={snap['power_required_W']:.1f}, stall={snap['stall_speed_ms']:.1f}"
        )

    violations_summary = []
    for v in state["violations"]:
        violations_summary.append(
            f"- Parameter: {v.parameter}, limit: {v.limit:.4f}, actual: {v.actual:.4f}, "
            f"severity: {v.severity:+.1%}, suggestion: {v.suggestion}"
        )

    user_message = f"""
Current iteration: {state['iteration']}
Maximum iterations: {state['max_iterations']}

Competition Rules:
- MTOW Limit: {state['rules'].mtow_limit_kg} kg
- Wingspan Limit: {state['rules'].wingspan_limit_m} m
- Power Limit: {state['rules'].power_limit_W} W
- Stall Speed Limit: {state['rules'].stall_speed_limit_ms} m/s
- Target Cruise Speed: {state['rules'].V_cruise_target_ms} m/s
- Air Density: {state['rules'].rho} kg/m^3

Current Design Variables:
- S_m2 (Wing Area): {state['S_m2']:.4f} m^2
- AR (Aspect Ratio): {state['AR']:.2f}
- V_cruise_ms: {state['V_cruise_ms']:.2f} m/s
- span_m: {state['span_m']:.2f} m
- CL_cruise: {state['CL_cruise']:.4f}
- CL_max: {state['CL_max']:.4f}
- CD0: {state['CD0']:.4f}

Current Violations:
{chr(10).join(violations_summary)}

Iteration History:
{chr(10).join(history_summary)}

Respond ONLY with a raw JSON object matching the schema:
{{
  "S_m2": float,
  "AR": float,
  "V_cruise_ms": float,
  "reasoning": "Brief explanation of changes"
}}
"""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.1,
        )
        content_text = response.content[0].text.strip()
        
        # Clean markdown wrappers if present
        if content_text.startswith("```json"):
            content_text = content_text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
        elif content_text.startswith("```"):
            content_text = content_text.split("```", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(content_text)
        
        # Sane validation of values returned by LLM
        S_m2 = float(data["S_m2"])
        AR = float(data["AR"])
        V_cruise_ms = float(data["V_cruise_ms"])
        reasoning = str(data["reasoning"])

        # Clamp check to prevent garbage
        S_m2 = max(0.04, min(S_m2, 10.0))
        AR = max(3.0, min(AR, 12.0))
        min_speed = state.get("stall_speed_ms", 10.0) * 1.15
        V_cruise_ms = max(min_speed, min(V_cruise_ms, state["rules"].V_cruise_target_ms * 1.5))

        logger.info("LLM Adjustment: S_m2=%.4f, AR=%.2f, V_cruise=%.2f. Reasoning: %s",
                    S_m2, AR, V_cruise_ms, reasoning)

        return {
            "S_m2": S_m2,
            "AR": AR,
            "V_cruise_ms": V_cruise_ms,
            "reasoning": f"LLM adjustment (iteration {state['iteration']}): {reasoning}",
            "iteration": state["iteration"] + 1,
        }

    except Exception as exc:
        logger.error("Failed to run LLM adjustment or parse response: %s. Falling back.", exc)
        return _adjust_deterministic(state)


def adjust_design(state: DesignState) -> dict:
    """Adjusts S_m2, AR, and V_cruise_ms using either LLM or deterministic rule fallback."""
    if state.get("use_llm", False):
        return _adjust_llm(state)
    else:
        return _adjust_deterministic(state)

# API Contract — UAV Design System (Phase 4/5 Frozen Interface)

**Status: FROZEN once Phase 4 dispatch begins.** Phase 4 (FastAPI) and Phase 5 (React) build against this document in parallel. If the shape needs to change, update this file first, then both layers — never let either layer silently drift from it.

This mirrors the `finalize_design` output from the Phase 3 LangGraph layer (see `agents/state.py`, `agents/nodes/finalize_design.py`).

---

## Endpoint: `POST /api/v1/design`

### Request Body

```json
{
  "competition_rules": {
    "MTOW_kg": 5.0,
    "payload_kg": 1.5,
    "max_wingspan_m": 2.0,
    "KV_rating": 1000,
    "max_power_W": 500,
    "min_stall_speed_ms": null,
    "target_cruise_speed_ms": 15.0,
    "custom_airfoil_paths": []
  },
  "use_llm": true,
  "max_iterations": 10
}
```

| Field | Type | Notes |
|---|---|---|
| `competition_rules` | object | Maps to Phase 3's `CompetitionRules` dataclass. Add/remove fields here as competition inputs change — this is the single source of truth for what "input" means. |
| `target_cruise_speed_ms` | float, optional | **Added during Phase 4 planning.** Required by the Phase 3 agent to initialize the aerodynamic solver but was missing from the original contract. Default `15.0` if omitted — this default lives here, in the contract, not buried in FastAPI code. |
| `custom_airfoil_paths` | list[str] | UIUC airfoil IDs, or filesystem paths to `.dat` files **on the same machine running the FastAPI server** (local single-user tool, not a multi-user upload service — no multipart upload endpoint exists or is planned). Validated server-side via `validate_dat_file()` before use. |
| `use_llm` | bool | `false` forces the deterministic fallback path in `adjust_design` (no Claude API call). Useful for CI/tests and for a "fast mode" toggle in the dashboard. |
| `max_iterations` | int | Optional override of the default 10. |

### Response Body (200 OK)

```json
{
  "status": "converged",
  "iterations_used": 4,
  "converged": true,

  "design": {
    "wing_area_m2": 0.85,
    "aspect_ratio": 8.2,
    "airfoil_id": "clarky",
    "CL_cruise": 0.52,
    "CD_total": 0.031,
    "MTOW_kg": 5.0,
    "stall_speed_ms": 9.1,
    "L_D_ratio": 16.8,
    "span_m": 2.64,
    "power_required_W": 187.3
  },

  "design_variables": {
    "V_cruise_ms": 14.5,
    "S_m2": 0.85,
    "AR": 8.2,
    "e": 0.78,
    "CD0": 0.021,
    "CL_max": 1.39,
    "Re": 210000
  },

  "violations": [],

  "history": [
    {
      "iteration": 1,
      "design_variables": { "...": "snapshot at this iteration" },
      "violations": [
        {
          "parameter": "span_m",
          "limit": 2.0,
          "actual": 2.9,
          "severity": "hard",
          "suggestion": "reduce aspect ratio or wing area"
        }
      ],
      "reasoning": "LLM or fallback explanation for the adjustment made this iteration"
    }
  ],

  "candidate_airfoils_considered": ["clarky", "s1223", "e387", "..."],
  "airfoil_selection_reasoning": "clarky selected: highest L/D at target Re among feasible candidates"
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | string enum | `"converged"` \| `"best_effort"` (hit max_iterations) \| `"no_viable_airfoil"` (2 consecutive iterations, no candidate fit) |
| `design` | object | **Exactly the 10 AGENTS.md shared keys.** Do not add fields here — extend `design_variables` instead if something new is needed. This keeps the frozen shared-state contract from Phase 1–3 intact. |
| `design_variables` | object | The 7 tunable inputs (not shared keys) from Phase 3's state schema. |
| `violations` | array | Empty if converged. Same `Violation` shape as Phase 3. |
| `history` | array | One entry per iteration, oldest first. Dashboard uses this to render the convergence trace / iteration-by-iteration story. |
| `candidate_airfoils_considered` | array[str] | Curated 10 + any valid custom airfoils supplied. |

### Error Responses

| Code | Meaning |
|---|---|
| `422` | Request validation failure — either malformed `competition_rules` (e.g. missing `MTOW_kg`) or a custom `.dat` file that failed `validate_dat_file()`. Response includes which field/file failed and why. |
| `500` | Unhandled backend error — should be rare given Phase 3's "never crash, log violations instead" design principle |

---

## Persistence Endpoint (deferred from Phase 3, lives here)

### `GET /api/v1/design/{design_id}`
Returns a previously computed design by ID (SQLite-backed, per the Phase 3 deferral decision).

### `GET /api/v1/design/history?limit=20`
List recent design runs for the dashboard's history view.

*(Exact SQLite schema for these two is FastAPI's call to make during Phase 4 — not frozen here, since React only needs the JSON shape above, not the storage implementation.)*

---

## Rules for Both Layers

1. **FastAPI must not rename or restructure the `design` object's 10 keys.** They are frozen since Phase 1 — this contract just exposes them over HTTP unchanged.
2. **React must not assume any field exists beyond what's listed here.** If the dashboard needs something new (e.g. a plot-ready time series), add it to this doc first, then to both layers.
3. If FastAPI's real output ever diverges from this doc, the doc is out of date — fix the doc immediately so React isn't building against stale assumptions.

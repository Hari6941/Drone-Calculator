# Fixed-Wing UAV Design Intelligence System

A multi-layer engineering tool that takes competition-style design constraints (MTOW, payload, wingspan limits, power budget) and computes a converged, physically-valid fixed-wing UAV configuration — including wing sizing, airfoil selection, and performance metrics — using a deterministic physics core combined with an AI-driven iterative optimization loop.

> **Status:** All 5 architectural layers complete and verified. Backend (FastAPI) and frontend (React dashboard) tested end-to-end against real XFOIL computations. Project naming, deployment, and polish are in progress.

---

## What it does

Given a set of competition rules like:

```json
{
  "MTOW_kg": 5.0,
  "payload_kg": 1.5,
  "max_wingspan_m": 2.0,
  "KV_rating": 1000,
  "max_power_W": 500,
  "target_cruise_speed_ms": 15.0
}
```

the system runs an iterative design loop that:

1. Seeds an initial wing sizing and cruise condition
2. Evaluates aerodynamics and performance (lift, drag, stall speed, power required)
3. Searches a curated airfoil database, running real **XFOIL** analysis on each candidate at the design Reynolds number
4. Selects the best-fit airfoil and adjusts design variables if constraints are violated
5. Repeats until convergence, a best-effort result, or a determination that no viable airfoil exists — logging the reasoning at every step

The result is a full performance breakdown (wing area, aspect ratio, CL/CD, L/D ratio, stall speed, power required) plus an iteration-by-iteration trace of *why* each decision was made.

---

## Architecture

Five layers, each consuming only the outputs of the ones before it — no layer reaches back to modify an earlier one:

```
Input Parser  →  Physics Engine  →  Airfoil Engine  →  LangGraph Multi-Agent  →  Output Dashboard / API
```

| Layer | Responsibility |
|---|---|
| **Physics Engine** | Deterministic aerodynamics and sizing math (frozen first, before any AI touches the pipeline) |
| **Airfoil Engine** | XFOIL-driven airfoil analysis and candidate filtering against a curated UIUC airfoil database |
| **LangGraph Multi-Agent** | 7-node orchestration graph that drives the iterative design/adjustment loop, with an LLM-backed reasoning step (and a deterministic fallback path) |
| **FastAPI Backend** | Exposes the pipeline over HTTP, persists design history (SQLite), serves the frozen API contract |
| **React Dashboard** | Interactive frontend for running designs, browsing history, and inspecting convergence traces |

The **API contract** between the backend and frontend layers (`docs/api_contract.md`) was frozen before backend and frontend development began, so both could be built in parallel without drifting apart.

---

## Tech Stack

- **Physics / Airfoil Engine:** Python, XFOIL (via subprocess), UIUC airfoil database parsing
- **Orchestration:** LangGraph, Claude API (with deterministic fallback for CI/offline use)
- **Backend:** FastAPI, SQLite, Pydantic
- **Frontend:** React (Vite), vanilla CSS, dark theme dashboard
- **Testing:** pytest (physics/airfoil/orchestration layers), manual endpoint verification via `Invoke-RestMethod`

---

## Project Status

| Layer | Status |
|---|---|
| Physics Engine | ✅ Done, tested |
| Airfoil Engine (XFOIL) | ✅ Done, tested (CL_max tolerance widened ±20% for documented low-Re XFOIL bias) |
| LangGraph Orchestration (7 nodes) | ✅ Done, 16/16 tests passing |
| API Contract | ✅ Frozen |
| FastAPI Backend | ✅ Done, 19/19 tests passing, manually verified against real requests |
| React Dashboard | ✅ Done, verified against both mock data and live backend/XFOIL runs |

### Known backlog (non-blocking)
- File handle leak in airfoil download/parsing under repeated calls
- One dead airfoil source URL in the curated list
- A couple of deprecation warnings to clean up (`datetime.utcnow()`, a deprecated FastAPI status constant)
- Final project naming still TBD

---

## Running Locally

**Backend:**
```bash
uvicorn api.main:app --reload --port 8000
```

**Frontend:**
```bash
cd dashboard
npm install
npm run dev
```

The dashboard supports a **Mock Mode** (simulated responses, useful for UI development without running the full physics/XFOIL pipeline) and **Live API** mode (connects to the real backend above).

---

## Author

Built by [Hari](https://github.com/Hari6941) — B.Tech Aerospace Engineering.

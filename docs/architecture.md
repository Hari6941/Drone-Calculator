# Architecture: Fixed Wing UAV Design Intelligence System

## Purpose
A web-based tool that takes competition/mission rules (payload, MTOW,
KV rating, wingspan constraints) as input and produces a validated,
physics-checked UAV design spec as output — wing sizing, airfoil
selection, and performance figures (L/D, stall speed, power required).

## Design principle
Physics engine first, AI on top. The multi-agent layer reasons over
and iterates on outputs from a validated, deterministic physics core —
it never generates aerodynamic numbers itself. Bad math produces
garbage agent output regardless of how good the reasoning layer is,
so correctness is enforced bottom-up, not delegated to the LLM.

## 5-Layer Architecture

```
Input Parser  ->  Physics Engine  ->  Airfoil Engine  ->  Multi-Agent AI  ->  Output Dashboard
```

### 1. Input Parser
Takes raw competition/mission rules (text or form input) and converts
them into a structured constraints dict: payload_kg, MTOW_limit_kg,
KV_range, wingspan_limit_m, mission profile (cruise speed, range, etc).

### 2. Physics Engine (`physics_engine.py`)
Pure, deterministic aerodynamic/performance functions. No I/O, no
framework dependencies beyond NumPy. Computes lift coefficient, drag
polar, L/D ratio, stall speed, and power required for a given design
point. Frozen once validated — status: VALIDATED (10/10 tests passing,
checked against Cessna 172 reference data and physical identities).

### 3. Airfoil Engine (`airfoil_engine/`)
Combines a UIUC airfoil database parser with an XFOIL subprocess
wrapper. The database is used for fast lookups; XFOIL is invoked
directly for custom Reynolds numbers or airfoils not in the database.
Filters and ranks candidate airfoils against a target CL_cruise and
Reynolds number. Status: IN PROGRESS.

### 4. Multi-Agent AI (`agents/`)
LangGraph orchestration layer. Iterates between the physics engine and
airfoil engine to converge on a design that satisfies the input
constraints, using a feedback loop rather than a single-pass
calculation — if a candidate design violates a constraint (e.g. stall
speed too high), the agent adjusts wing area or airfoil choice and
re-evaluates rather than failing outright. Status: NOT STARTED.

### 5. Output Dashboard
FastAPI backend exposing the physics/airfoil/agent layers as
endpoints; React frontend for input forms, results tables, and
performance charts (e.g. L/D vs CL). Also generates a PDF design
report via ReportLab. Status: NOT STARTED.

## Shared State Dict Schema
All layers pass state through a single dict, defined in AGENTS.md as
the source of truth:

| Key | Meaning | Unit |
|---|---|---|
| wing_area_m2 | Wing reference area | m^2 |
| aspect_ratio | Wingspan^2 / wing_area | dimensionless |
| airfoil_id | Selected airfoil identifier | string |
| CL_cruise | Cruise lift coefficient | dimensionless |
| CD_total | Total drag coefficient | dimensionless |
| MTOW_kg | Max takeoff weight | kg |
| stall_speed_ms | Stall speed | m/s |
| L_D_ratio | Lift-to-drag ratio | dimensionless |
| span_m | Wingspan | m |
| power_required_W | Power required for cruise | W |

## Tech Stack
- Backend: Python 3.11, FastAPI
- Physics/numerics: NumPy, SciPy
- Airfoil analysis: XFOIL (subprocess), UIUC Airfoil Database
- Agent orchestration: LangGraph, Claude API (Sonnet)
- Storage: SQLite
- Reporting: ReportLab (PDF generation)
- Frontend: React

## Build Order (do not skip ahead — each layer depends on the previous)
1. Physics engine — pure functions, validated against known
   aircraft/textbook data before anything else is built.
2. Airfoil engine — UIUC parser + XFOIL wrapper, validated against
   published polar data for known airfoils (NACA 0012, Clark Y).
3. Multi-agent layer — LangGraph graph consuming layers 1-2 only.
   Plan reviewed before implementation (architectural risk is highest
   here — feedback loop and convergence logic).
4. API layer — FastAPI endpoints exposing layers 1-3.
5. Dashboard — React frontend consuming the API layer only, no direct
   imports from physics_engine or airfoil_engine.

Layers 4 and 5 can be built in parallel once layers 1-3 are validated,
since they are loosely coupled to each other.

## 12-Week Roadmap (high level)
- Weeks 1-2: Physics engine, validated
- Weeks 3-5: Airfoil engine (UIUC parser, XFOIL wrapper, filtering)
- Weeks 6-8: Multi-agent orchestration layer
- Weeks 9-10: FastAPI backend
- Weeks 10-12: React dashboard, PDF report generation, end-to-end
  testing against real competition rule sets

## Non-Goals (for this version)
- No structural/FEA analysis (wing spar sizing, load cases)
- No propulsion system CAD — motor/prop selection is parametric only
  (KV, power required), not detailed electrical design
- No real-time flight simulation — this is a design-time tool, not a
  flight dynamics simulator

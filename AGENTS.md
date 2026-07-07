# Project: Fixed Wing UAV Design Intelligence System

## Non-negotiables
- All units are SI (meters, kg, seconds, Newtons, Watts). No mixed units, ever.
- Shared state dict keys (do not rename or add without updating this file):
  wing_area_m2, aspect_ratio, airfoil_id, CL_cruise, CD_total, MTOW_kg,
  stall_speed_ms, L_D_ratio, span_m, power_required_W
- physics_engine.py is FROZEN once validated. Do not modify it from any
  other layer's task. If a bug is found, flag it, don't silently patch it.
- Every physics/aero function must have a docstring stating the source
  equation (e.g. "Anderson, Fundamentals of Aerodynamics, eq 5.XX").

## Architecture (build in this order, do not skip ahead)
1. physics_engine.py — pure functions, no I/O, no dependencies beyond numpy
2. airfoil_engine/ — UIUC .dat parser + XFOIL subprocess wrapper
3. agents/ — LangGraph orchestration, consumes layers 1-2 only
4. api/ — FastAPI, exposes layer 1-3 as endpoints
5. dashboard/ — React frontend, consumes api/ only

## Tech stack
Python 3.11, NumPy/SciPy, FastAPI, LangGraph, Claude API (Sonnet),
SQLite, ReportLab, React (frontend)

## Testing
Every new module needs a test file with at least 2 hand-calculated or
literature-sourced validation cases before being marked done.

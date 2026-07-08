"""
test_api.py

Integration and validation tests for the FastAPI endpoint layer.
"""

from pathlib import Path
import pytest
import sqlite3
from fastapi.testclient import TestClient

from api.main import app
from api.database import init_db

# Helper client fixture
@pytest.fixture
def client(tmp_path):
    # Setup in-memory / temporary database path for isolation during test
    test_db = tmp_path / "test_designs.db"
    init_db(db_path=test_db)
    
    # We patch routes' database connection path or simply use default connection
    # since routes.py uses get_db_path() we can patch api.database._DEFAULT_DB_PATH
    import api.database
    original_db = api.database._DEFAULT_DB_PATH
    api.database._DEFAULT_DB_PATH = test_db
    
    with TestClient(app) as c:
        yield c
        
    api.database._DEFAULT_DB_PATH = original_db


def test_post_design_success(client):
    """POST /api/v1/design succeeds under feasible parameters and returns correct shape."""
    payload = {
        "competition_rules": {
            "MTOW_kg": 4.0,
            "payload_kg": 1.2,
            "max_wingspan_m": 1.8,
            "KV_rating": 800,
            "max_power_W": 300,
            "min_stall_speed_ms": 12.0,
            "target_cruise_speed_ms": 16.0,
            "custom_airfoil_paths": []
        },
        "use_llm": False,
        "max_iterations": 3
    }
    
    response = client.post("/api/v1/design", json=payload)
    assert response.status_code == 200, f"Error: {response.json()}"
    data = response.json()
    
    assert "id" in data
    assert "created_at" in data
    assert "status" in data
    assert data["converged"] is True
    
    # Validate the 10 AGENTS.md contract keys
    design = data["design"]
    required_keys = [
        "wing_area_m2", "aspect_ratio", "airfoil_id", "CL_cruise", 
        "CD_total", "MTOW_kg", "stall_speed_ms", "L_D_ratio", 
        "span_m", "power_required_W"
    ]
    for key in required_keys:
        assert key in design
        if key != "airfoil_id":
            assert design[key] > 0
            
    # Validate design_variables
    design_vars = data["design_variables"]
    for v in ["V_cruise_ms", "S_m2", "AR", "e", "CD0", "CL_max", "Re"]:
        assert v in design_vars
        assert design_vars[v] > 0
        
    assert "history" in data
    assert len(data["history"]) > 0
    assert data["history"][0]["iteration"] == 1


def test_get_design_by_id_and_history(client):
    """GET /api/v1/design/{id} and /api/v1/design/history load the saved run from SQLite."""
    payload = {
        "competition_rules": {
            "MTOW_kg": 3.0,
            "payload_kg": 1.0,
            "max_wingspan_m": 1.5,
            "V_cruise_target_ms": 15.0,  # mapped from default
            "custom_airfoil_paths": []
        },
        "use_llm": False,
        "max_iterations": 2
    }
    
    # 1. POST to generate database entry
    post_resp = client.post("/api/v1/design", json=payload)
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    design_id = post_data["id"]
    
    # 2. GET by ID
    get_resp = client.get(f"/api/v1/design/{design_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["id"] == design_id
    assert get_data["converged"] == post_data["converged"]
    assert get_data["design"]["wing_area_m2"] == post_data["design"]["wing_area_m2"]
    
    # 3. GET history
    hist_resp = client.get("/api/v1/design/history?limit=5")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert len(hist_data) >= 1
    assert hist_data[0]["id"] == design_id

    # Test non-existent ID
    bad_resp = client.get("/api/v1/design/missing-uuid-123")
    assert bad_resp.status_code == 404


def test_post_design_validation_errors(client, tmp_path):
    """Verify input validation and custom .dat file 422 details."""
    # 1. Invalid input (missing MTOW_kg)
    bad_payload = {
        "competition_rules": {
            "payload_kg": 1.0,
            "max_wingspan_m": 1.5
        }
    }
    resp = client.post("/api/v1/design", json=bad_payload)
    assert resp.status_code == 422  # Pydantic validation error code
    
    # 2. Custom dat validation failure: non-existent file
    missing_file_payload = {
        "competition_rules": {
            "MTOW_kg": 3.0,
            "payload_kg": 1.0,
            "max_wingspan_m": 1.5,
            "custom_airfoil_paths": ["data/user_airfoils/nonexistent.dat"]
        }
    }
    resp = client.post("/api/v1/design", json=missing_file_payload)
    assert resp.status_code == 422
    assert "reason" in resp.json()["detail"]
    assert "does not exist" in resp.json()["detail"]["reason"]
    
    # 3. Custom dat validation failure: invalid chord length
    project_root = Path(__file__).resolve().parent.parent
    whitelist_dir = project_root / "data" / "user_airfoils"
    whitelist_dir.mkdir(parents=True, exist_ok=True)
    bad_dat = whitelist_dir / "bad_chord.dat"
    bad_dat.write_text("Bad Chord Airfoil\n0.0 0.0\n0.2 0.02\n0.4 0.01\n0.2 -0.02\n0.0 0.0\n0.1 0.01\n0.1 -0.01\n0.3 0.01\n0.3 -0.01\n0.05 0.0\n")
    try:
        bad_chord_payload = {
            "competition_rules": {
                "MTOW_kg": 3.0,
                "payload_kg": 1.0,
                "max_wingspan_m": 1.5,
                "custom_airfoil_paths": ["data/user_airfoils/bad_chord.dat"]
            }
        }
        resp = client.post("/api/v1/design", json=bad_chord_payload)
        assert resp.status_code == 422
        data = resp.json()["detail"]
        assert "chord length" in data["reason"]
    finally:
        if bad_dat.exists():
            bad_dat.unlink()


def test_concurrency_lock(client):
    """Verify that concurrent design optimization requests are rejected with a 429 status code."""
    from unittest.mock import patch

    with patch("api.routes._design_lock.locked", return_value=True):
        payload = {
            "competition_rules": {
                "MTOW_kg": 4.0,
                "payload_kg": 1.2,
                "max_wingspan_m": 1.8,
                "custom_airfoil_paths": []
            }
        }
        response = client.post("/api/v1/design", json=payload)
        assert response.status_code == 429
        assert "Another design optimization run is currently in progress." in response.json()["detail"]


def test_custom_path_whitelist_validation(client):
    """Verify that custom airfoil paths are restricted to data/user_airfoils/ and reject path traversal."""
    import os

    # 1. Reject path containing '..' (should return 400 Bad Request)
    payload_dotdot = {
        "competition_rules": {
            "MTOW_kg": 4.0,
            "payload_kg": 1.2,
            "max_wingspan_m": 1.8,
            "custom_airfoil_paths": ["data/user_airfoils/../../etc/passwd"]
        }
    }
    response = client.post("/api/v1/design", json=payload_dotdot)
    assert response.status_code == 400
    assert "Access denied" in response.json()["detail"]

    # 2. Reject path resolving outside data/user_airfoils/
    outside_path = "C:/absolute/outside.dat" if os.name == "nt" else "/absolute/outside.dat"
    payload_outside = {
        "competition_rules": {
            "MTOW_kg": 4.0,
            "payload_kg": 1.2,
            "max_wingspan_m": 1.8,
            "custom_airfoil_paths": [outside_path]
        }
    }
    response = client.post("/api/v1/design", json=payload_outside)
    assert response.status_code == 400
    assert "Access denied" in response.json()["detail"]

    # 3. Allow valid path under data/user_airfoils/ (which fails with 422 because the file does not exist, not 400)
    payload_valid = {
        "competition_rules": {
            "MTOW_kg": 4.0,
            "payload_kg": 1.2,
            "max_wingspan_m": 1.8,
            "custom_airfoil_paths": ["data/user_airfoils/nonexistent.dat"]
        }
    }
    response = client.post("/api/v1/design", json=payload_valid)
    assert response.status_code == 422
    assert "does not exist" in response.json()["detail"]["reason"]


def test_cors_origins(client):
    """Verify that CORS allow_origins is restricted to the localhost origins."""
    # 1. Allowed Origin
    headers_allowed = {"Origin": "http://localhost:5173"}
    response = client.get("/", headers=headers_allowed)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # 2. Disallowed Origin
    headers_disallowed = {"Origin": "http://malicious.com"}
    response = client.get("/", headers=headers_disallowed)
    assert response.headers.get("access-control-allow-origin") is None


def test_design_stream_success(client):
    """Verify that POST /api/v1/design/stream returns a text/event-stream containing node updates and complete status."""
    import json
    payload = {
        "competition_rules": {
            "MTOW_kg": 4.0,
            "payload_kg": 1.2,
            "max_wingspan_m": 1.8,
            "KV_rating": 800,
            "max_power_W": 300,
            "min_stall_speed_ms": 12.0,
            "target_cruise_speed_ms": 16.0,
            "custom_airfoil_paths": []
        },
        "use_llm": False,
        "max_iterations": 2
    }

    response = client.post("/api/v1/design/stream", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    events = []
    for line in response.iter_lines():
        if line:
            line_str = line.decode("utf-8") if isinstance(line, bytes) else line
            if line_str.startswith("data: "):
                event_data = json.loads(line_str[6:])
                events.append(event_data)

    # Check that we received event data and a 'complete' event containing the result payload
    assert len(events) > 0
    complete_event = next((e for e in events if e.get("type") == "complete"), None)
    assert complete_event is not None
    result = complete_event["result"]
    assert "id" in result
    assert "status" in result
    assert result["converged"] is True



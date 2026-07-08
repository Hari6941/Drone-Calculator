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
            "custom_airfoil_paths": [str(tmp_path / "nonexistent.dat")]
        }
    }
    resp = client.post("/api/v1/design", json=missing_file_payload)
    assert resp.status_code == 422
    assert "reason" in resp.json()["detail"]
    assert "does not exist" in resp.json()["detail"]["reason"]
    
    # 3. Custom dat validation failure: invalid chord length
    bad_dat = tmp_path / "bad_chord.dat"
    bad_dat.write_text("Bad Chord Airfoil\n0.0 0.0\n0.2 0.02\n0.4 0.01\n0.2 -0.02\n0.0 0.0\n0.1 0.01\n0.1 -0.01\n0.3 0.01\n0.3 -0.01\n0.05 0.0\n")
    bad_chord_payload = {
        "competition_rules": {
            "MTOW_kg": 3.0,
            "payload_kg": 1.0,
            "max_wingspan_m": 1.5,
            "custom_airfoil_paths": [str(bad_dat)]
        }
    }
    resp = client.post("/api/v1/design", json=bad_chord_payload)
    assert resp.status_code == 422
    data = resp.json()["detail"]
    assert "chord length" in data["reason"]

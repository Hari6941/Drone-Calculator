"""
database.py

SQLite database helper module for persisting design optimization runs.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "designs.db"

def get_db_path() -> Path:
    """Returns the resolved absolute path to the SQLite database file."""
    path = Path(_DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes the database and creates the designs table if it does not exist."""
    path = db_path or get_db_path()
    with sqlite3.connect(str(path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS designs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_kg REAL NOT NULL,
                mtow_limit_kg REAL NOT NULL,
                wingspan_limit_m REAL NOT NULL,
                status TEXT NOT NULL,
                converged INTEGER NOT NULL,
                response_json TEXT NOT NULL
            )
        """)
        conn.commit()

def save_design(
    design_id: str,
    created_at: str,
    payload_kg: float,
    mtow_limit_kg: float,
    wingspan_limit_m: float,
    status: str,
    converged: bool,
    response_json: str,
    db_path: Optional[Path] = None,
) -> None:
    """Saves a completed design run to the database."""
    path = db_path or get_db_path()
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            """
            INSERT INTO designs (id, created_at, payload_kg, mtow_limit_kg, wingspan_limit_m, status, converged, response_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                design_id,
                created_at,
                payload_kg,
                mtow_limit_kg,
                wingspan_limit_m,
                status,
                int(converged),
                response_json,
            ),
        )
        conn.commit()

def get_design_by_id(design_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Loads a single design run's response JSON from the database by its ID."""
    path = db_path or get_db_path()
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT response_json FROM designs WHERE id = ?", (design_id,))
        row = cur.fetchone()
        if row:
            return json.loads(row["response_json"])
    return None

def get_design_history(limit: int = 20, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Lists recent design runs ordered by creation time descending."""
    path = db_path or get_db_path()
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT response_json FROM designs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [json.loads(row["response_json"]) for row in rows]

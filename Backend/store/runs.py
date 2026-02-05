"""CRUD operations for the runs table."""

import json
import logging
from datetime import datetime

from store.db import get_connection

logger = logging.getLogger(__name__)


def create_run(run_id: str, input_type: str, raw_input: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO runs (run_id, input_type, raw_input, status) VALUES (?, ?, ?, 'pending')",
            (run_id, input_type, raw_input[:10000]),  # truncate very long inputs
        )
        conn.commit()
    finally:
        conn.close()


def update_run(run_id: str, **fields) -> None:
    """Update specific fields of a run. JSON-serializable values are auto-serialized."""
    conn = get_connection()
    try:
        sets = []
        vals = []
        for k, v in fields.items():
            if k in ("extracted_json", "evidence_json", "reply_draft", "actions_json") and not isinstance(v, str):
                v = json.dumps(v, ensure_ascii=False, default=str)
            sets.append(f"{k} = ?")
            vals.append(v)
        sets.append("updated_at = ?")
        vals.append(datetime.utcnow().isoformat())
        vals.append(run_id)
        sql = f"UPDATE runs SET {', '.join(sets)} WHERE run_id = ?"
        conn.execute(sql, vals)
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        # Parse JSON fields
        for jf in ("extracted_json", "evidence_json", "reply_draft", "actions_json"):
            if d.get(jf):
                try:
                    d[jf] = json.loads(d[jf])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
    finally:
        conn.close()


def list_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT run_id, created_at, input_type, status, error FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Cache helpers ---

def cache_get(key: str) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value_json FROM cache WHERE key = ? AND (julianday('now') - julianday(created_at)) * 86400 < ttl_seconds",
            (key,),
        ).fetchone()
        return row["value_json"] if row else None
    finally:
        conn.close()


def cache_set(key: str, value: str, ttl: int = 3600) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value_json, ttl_seconds) VALUES (?, ?, ?)",
            (key, value, ttl),
        )
        conn.commit()
    finally:
        conn.close()

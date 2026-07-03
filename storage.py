from __future__ import annotations

"""SQLite persistence for builder-made strategies and the marketplace.

Ownership is anonymous by default: the frontend holds a backend-issued token
(localStorage) and sends it as X-Anon-Token. No account is required.
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "arena.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS custom_strategies (
    id TEXT PRIMARY KEY,
    owner_token TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    definition TEXT NOT NULL,
    python_source TEXT NOT NULL,
    published INTEGER NOT NULL DEFAULT 0,
    forked_from TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_custom_owner ON custom_strategies(owner_token);
CREATE INDEX IF NOT EXISTS idx_custom_published ON custom_strategies(published);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def issue_token() -> str:
    return uuid.uuid4().hex


def _row_to_dict(row: sqlite3.Row, include_definition: bool = True) -> dict:
    data = {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "published": bool(row["published"]),
        "forked_from": row["forked_from"],
        "created_at": row["created_at"],
        "author": row["owner_token"][:6],
    }
    if include_definition:
        data["definition"] = json.loads(row["definition"])
        data["python_source"] = row["python_source"]
    return data


def save_strategy(
    owner_token: str,
    name: str,
    description: str,
    definition: dict,
    python_source: str,
    forked_from: str | None = None,
) -> dict:
    strategy_id = f"custom:{uuid.uuid4().hex[:8]}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO custom_strategies (id, owner_token, name, description, definition,"
            " python_source, published, forked_from, created_at) VALUES (?,?,?,?,?,?,0,?,?)",
            (
                strategy_id,
                owner_token,
                name.strip()[:60],
                description.strip()[:400],
                json.dumps(definition),
                python_source,
                forked_from,
                time.time(),
            ),
        )
    return get_strategy(strategy_id)


def update_strategy(strategy_id: str, owner_token: str, name: str, description: str,
                    definition: dict, python_source: str) -> dict | None:
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE custom_strategies SET name=?, description=?, definition=?, python_source=?"
            " WHERE id=? AND owner_token=?",
            (name.strip()[:60], description.strip()[:400], json.dumps(definition),
             python_source, strategy_id, owner_token),
        )
        if cursor.rowcount == 0:
            return None
    return get_strategy(strategy_id)


def get_strategy(strategy_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM custom_strategies WHERE id=?", (strategy_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_owned(owner_token: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM custom_strategies WHERE owner_token=? ORDER BY created_at DESC",
            (owner_token,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_published() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM custom_strategies WHERE published=1 ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def set_published(strategy_id: str, owner_token: str, published: bool) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE custom_strategies SET published=? WHERE id=? AND owner_token=?",
            (int(published), strategy_id, owner_token),
        )
        return cursor.rowcount > 0


def delete_strategy(strategy_id: str, owner_token: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM custom_strategies WHERE id=? AND owner_token=?",
            (strategy_id, owner_token),
        )
        return cursor.rowcount > 0


def fork_strategy(strategy_id: str, new_owner_token: str) -> dict | None:
    original = get_strategy(strategy_id)
    if original is None or not original["published"]:
        return None
    return save_strategy(
        owner_token=new_owner_token,
        name=f"{original['name']} (fork)",
        description=original["description"],
        definition=original["definition"],
        python_source=original["python_source"],
        forked_from=strategy_id,
    )

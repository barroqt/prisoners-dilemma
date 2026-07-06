from __future__ import annotations

"""SQLite persistence for builder-made strategies, the marketplace, and accounts.

Ownership is anonymous by default: the frontend holds a backend-issued token
(localStorage) and sends it as X-Anon-Token. No account is required.

Accounts are strictly optional. A user may register/login at any time, which
*links* their current anonymous token to the account: everything the token
owned (strategies, votes) is migrated to the account's owner key `user:<id>`,
and any browser that later logs in gets the same data. Anonymous users are
untouched by all of this — their owner key is simply the raw token.
"""

import hashlib
import hmac
import json
import os
import re
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

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- An anon token linked to an account acts as that account's session.
CREATE TABLE IF NOT EXISTS token_links (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    linked_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS votes (
    strategy_id TEXT NOT NULL,
    voter_key TEXT NOT NULL,
    value INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (strategy_id, voter_key)
);
"""

MAX_TAGS = 5
_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,19}$")

# author/vote/fork enrichment shared by every read that returns strategy rows
_STRATEGY_SELECT = """
SELECT cs.*, u.username AS author_name,
    (SELECT COUNT(*) FROM votes v WHERE v.strategy_id = cs.id AND v.value = 1) AS upvotes,
    (SELECT COUNT(*) FROM votes v WHERE v.strategy_id = cs.id AND v.value = -1) AS downvotes,
    (SELECT COUNT(*) FROM custom_strategies f WHERE f.forked_from = cs.id) AS fork_count,
    (SELECT v.value FROM votes v WHERE v.strategy_id = cs.id AND v.voter_key = :viewer) AS my_vote,
    (cs.owner_token = :viewer) AS is_mine
FROM custom_strategies cs
LEFT JOIN users u ON cs.owner_token = 'user:' || u.id
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(custom_strategies)")}
    if "tags" not in columns:
        conn.execute("ALTER TABLE custom_strategies ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
    return conn


def issue_token() -> str:
    return uuid.uuid4().hex


def normalize_tags(tags: list[str]) -> list[str]:
    """Lowercase, dedupe, and validate tags; raises ValueError on a bad tag."""
    cleaned: list[str] = []
    for raw in tags:
        tag = raw.strip().lower().replace(" ", "-")
        if not tag:
            continue
        if not _TAG_RE.match(tag):
            raise ValueError(
                f"Invalid tag '{raw}': use 1-20 letters, digits or dashes, starting with a letter or digit."
            )
        if tag not in cleaned:
            cleaned.append(tag)
    if len(cleaned) > MAX_TAGS:
        raise ValueError(f"At most {MAX_TAGS} tags allowed.")
    return cleaned


# ---------------------------------------------------------------------------
# Accounts (optional — anonymous tokens keep working without one)
# ---------------------------------------------------------------------------

_PBKDF2_ITERATIONS = 200_000


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest)
    except ValueError:
        return False


def _link_token(conn: sqlite3.Connection, token: str, user_id: int) -> None:
    """Attach the token to the account and hand the token's anonymous data over.

    Migrating owner keys (rather than keeping per-token ownership) is what lets
    the same account see its strategies from any logged-in browser.
    """
    owner_key = f"user:{user_id}"
    conn.execute(
        "INSERT OR REPLACE INTO token_links (token, user_id, linked_at) VALUES (?,?,?)",
        (token, user_id, time.time()),
    )
    conn.execute(
        "UPDATE custom_strategies SET owner_token=? WHERE owner_token=?", (owner_key, token)
    )
    # OR IGNORE: if the account already voted on the same strategy, keep its vote.
    conn.execute("UPDATE OR IGNORE votes SET voter_key=? WHERE voter_key=?", (owner_key, token))
    conn.execute("DELETE FROM votes WHERE voter_key=?", (token,))


def register(username: str, password: str, token: str) -> dict:
    with _connect() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                (username, _hash_password(password), time.time()),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Username is already taken.")
        _link_token(conn, token, cursor.lastrowid)
    return {"username": username}


def login(username: str, password: str, token: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if row is None or not _verify_password(password, row["password_hash"]):
            return None
        _link_token(conn, token, row["id"])
        return {"username": row["username"]}


def logout(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM token_links WHERE token=?", (token,))


def current_user(token: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT u.username FROM token_links t JOIN users u ON u.id = t.user_id WHERE t.token=?",
            (token,),
        ).fetchone()
    return {"username": row["username"]} if row else None


def resolve_owner(token: str) -> str:
    """The identity key data hangs off: `user:<id>` when logged in, else the token."""
    with _connect() as conn:
        row = conn.execute("SELECT user_id FROM token_links WHERE token=?", (token,)).fetchone()
    return f"user:{row['user_id']}" if row else token


# ---------------------------------------------------------------------------
# Custom strategies
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row, include_definition: bool = True) -> dict:
    keys = row.keys()
    data = {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "tags": json.loads(row["tags"]) if "tags" in keys else [],
        "published": bool(row["published"]),
        "forked_from": row["forked_from"],
        "created_at": row["created_at"],
        "author": (row["author_name"] if "author_name" in keys else None)
        or f"anon-{row['owner_token'][:6]}",
        "is_registered_author": bool("author_name" in keys and row["author_name"]),
    }
    for key in ("upvotes", "downvotes", "fork_count"):
        if key in keys:
            data[key] = row[key] or 0
    if "my_vote" in keys:
        data["my_vote"] = row["my_vote"] or 0
        data["score"] = data["upvotes"] - data["downvotes"]
    if "is_mine" in keys:
        data["is_mine"] = bool(row["is_mine"])
    if include_definition:
        data["definition"] = json.loads(row["definition"])
        data["python_source"] = row["python_source"]
    return data


def save_strategy(
    owner_key: str,
    name: str,
    description: str,
    definition: dict,
    python_source: str,
    tags: list[str] | None = None,
    forked_from: str | None = None,
) -> dict:
    strategy_id = f"custom:{uuid.uuid4().hex[:8]}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO custom_strategies (id, owner_token, name, description, definition,"
            " python_source, published, forked_from, created_at, tags) VALUES (?,?,?,?,?,?,0,?,?,?)",
            (
                strategy_id,
                owner_key,
                name.strip()[:60],
                description.strip()[:400],
                json.dumps(definition),
                python_source,
                forked_from,
                time.time(),
                json.dumps(tags or []),
            ),
        )
    return get_strategy(strategy_id)


def update_strategy(strategy_id: str, owner_key: str, name: str, description: str,
                    definition: dict, python_source: str, tags: list[str] | None = None) -> dict | None:
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE custom_strategies SET name=?, description=?, definition=?, python_source=?, tags=?"
            " WHERE id=? AND owner_token=?",
            (name.strip()[:60], description.strip()[:400], json.dumps(definition),
             python_source, json.dumps(tags or []), strategy_id, owner_key),
        )
        if cursor.rowcount == 0:
            return None
    return get_strategy(strategy_id)


def get_strategy(strategy_id: str, viewer_key: str = "") -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            _STRATEGY_SELECT + " WHERE cs.id=:id", {"id": strategy_id, "viewer": viewer_key}
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_owned(owner_key: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            _STRATEGY_SELECT + " WHERE cs.owner_token=:owner ORDER BY cs.created_at DESC",
            {"owner": owner_key, "viewer": owner_key},
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_published(viewer_key: str = "") -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            _STRATEGY_SELECT + " WHERE cs.published=1 ORDER BY cs.created_at DESC LIMIT 200",
            {"viewer": viewer_key},
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def set_published(strategy_id: str, owner_key: str, published: bool) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE custom_strategies SET published=? WHERE id=? AND owner_token=?",
            (int(published), strategy_id, owner_key),
        )
        return cursor.rowcount > 0


def delete_strategy(strategy_id: str, owner_key: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM custom_strategies WHERE id=? AND owner_token=?",
            (strategy_id, owner_key),
        )
        if cursor.rowcount == 0:
            return False
        conn.execute("DELETE FROM votes WHERE strategy_id=?", (strategy_id,))
        return True


def fork_strategy(strategy_id: str, new_owner_key: str) -> dict | None:
    original = get_strategy(strategy_id)
    if original is None or not original["published"]:
        return None
    return save_strategy(
        owner_key=new_owner_key,
        name=f"{original['name']} (fork)",
        description=original["description"],
        definition=original["definition"],
        python_source=original["python_source"],
        tags=original["tags"],
        forked_from=strategy_id,
    )


# ---------------------------------------------------------------------------
# Votes
# ---------------------------------------------------------------------------

def set_vote(strategy_id: str, voter_key: str, value: int) -> dict | None:
    """Casts (+1/-1), or clears (0), the voter's vote. Returns updated counts."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT owner_token, published FROM custom_strategies WHERE id=?", (strategy_id,)
        ).fetchone()
        if row is None or not row["published"]:
            return None
        if row["owner_token"] == voter_key:
            raise ValueError("You can't vote on your own strategy.")
        if value == 0:
            conn.execute(
                "DELETE FROM votes WHERE strategy_id=? AND voter_key=?", (strategy_id, voter_key)
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO votes (strategy_id, voter_key, value, created_at)"
                " VALUES (?,?,?,?)",
                (strategy_id, voter_key, value, time.time()),
            )
        counts = conn.execute(
            "SELECT COALESCE(SUM(value = 1), 0) AS up, COALESCE(SUM(value = -1), 0) AS down"
            " FROM votes WHERE strategy_id=?",
            (strategy_id,),
        ).fetchone()
    return {
        "id": strategy_id,
        "upvotes": counts["up"],
        "downvotes": counts["down"],
        "score": counts["up"] - counts["down"],
        "my_vote": value,
    }

"""OpenCode SQLite session reader."""
from __future__ import annotations

import json
import os
import platform
import sqlite3
from pathlib import Path

from headroom_cli.types import MessageInfo, PartInfo, SessionInfo


def get_db_path() -> Path:
    """Find OpenCode's SQLite database.

    Precedence: OPENCODE_DB env var > platform-specific default path.
    """
    env_path = os.environ.get("OPENCODE_DB")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p
        msg = f"OPENCODE_DB points to non-existent file: {env_path}"
        raise FileNotFoundError(msg)

    system = platform.system()
    if system == "Linux":
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        local_app = os.environ.get("LOCALAPPDATA")
        base = Path(local_app) if local_app else Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"

    db_path = base / "opencode" / "opencode.db"
    if db_path.is_file():
        return db_path

    msg = f"OpenCode database not found at {db_path}"
    raise FileNotFoundError(msg)


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a read-only connection to the database."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_rw(db_path: Path) -> sqlite3.Connection:
    """Open a read-write connection to the database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def list_sessions(
    db_path: Path,
    project_id: str | None = None,
) -> list[SessionInfo]:
    """List all sessions, newest first."""
    conn = _connect(db_path)
    try:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM session WHERE directory = ? ORDER BY time_updated DESC",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM session ORDER BY time_updated DESC",
            ).fetchall()
        return [_row_to_session(r) for r in rows]
    finally:
        conn.close()


def get_messages(db_path: Path, session_id: str) -> list[MessageInfo]:
    """Get all messages for a session, ordered by creation time."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM message WHERE session_id = ? ORDER BY time_created ASC",
            (session_id,),
        ).fetchall()
        return [_row_to_message(r) for r in rows]
    finally:
        conn.close()


def get_parts(db_path: Path, session_id: str) -> list[PartInfo]:
    """Get all parts for a session, ordered by message then creation time."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM part WHERE session_id = ? "
            "ORDER BY message_id, time_created ASC",
            (session_id,),
        ).fetchall()
        return [_row_to_part(r) for r in rows]
    finally:
        conn.close()


def get_session_data(
    db_path: Path,
    session_id: str,
) -> tuple[list[MessageInfo], list[PartInfo]]:
    """Get complete session data (messages + parts)."""
    messages = get_messages(db_path, session_id)
    parts = get_parts(db_path, session_id)
    return messages, parts


def _row_to_session(row: sqlite3.Row) -> SessionInfo:
    keys = row.keys()
    return SessionInfo(
        id=row["id"],
        title=row["title"] if "title" in keys else "",
        directory=row["directory"] if "directory" in keys else "",
        cost=float(row["cost"]) if "cost" in keys else 0.0,
        tokens_input=int(row["tokens_input"]) if "tokens_input" in keys else 0,
        tokens_output=int(row["tokens_output"]) if "tokens_output" in keys else 0,
        time_created=int(row["time_created"]) if "time_created" in keys else 0,
        time_updated=int(row["time_updated"]) if "time_updated" in keys else 0,
    )


def _row_to_message(row: sqlite3.Row) -> MessageInfo:
    keys = row.keys()
    raw_data = row["data"] if "data" in keys else "{}"
    data = json.loads(raw_data) if isinstance(raw_data, str) else {}
    return MessageInfo(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"] if "role" in keys else "unknown",
        time_created=int(row["time_created"]) if "time_created" in keys else 0,
        data=data,
    )


def _row_to_part(row: sqlite3.Row) -> PartInfo:
    keys = row.keys()
    raw_data = row["data"] if "data" in keys else "{}"
    data = json.loads(raw_data) if isinstance(raw_data, str) else {}
    serialized = raw_data if isinstance(raw_data, str) else json.dumps(data)
    return PartInfo(
        id=row["id"],
        message_id=row["message_id"],
        session_id=row["session_id"],
        part_type=row["type"] if "type" in keys else "unknown",
        time_created=int(row["time_created"]) if "time_created" in keys else 0,
        data=data,
        byte_size=len(serialized.encode("utf-8")),
    )

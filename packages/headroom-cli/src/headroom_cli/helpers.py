"""Shared utility functions."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from headroom_cli.types import PrescriptionResult


def emit(msg: str, *, end: str = "\n") -> None:
    """Write user-facing output to stdout."""
    sys.stdout.write(msg + end)
    sys.stdout.flush()


def emit_err(msg: str, *, end: str = "\n") -> None:
    """Write error/warning output to stderr."""
    sys.stderr.write(msg + end)
    sys.stderr.flush()


def format_bytes(n: int) -> str:
    """Format byte count as human-readable string."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def format_timestamp(ts: int) -> str:
    """Format a Unix timestamp as ISO-8601 local time."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate_str(s: str, max_len: int) -> str:
    """Truncate string to max_len, appending '...' if truncated."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def prescription_to_dict(result: PrescriptionResult) -> dict[str, object]:
    """Convert PrescriptionResult to a JSON-serializable dict."""
    return {
        "prescription": result.prescription,
        "total_bytes_saved": result.total_bytes_saved,
        "total_parts_affected": result.total_parts_affected,
        "strategies": [
            {
                "name": s.name,
                "bytes_saved": s.bytes_saved,
                "parts_affected": s.parts_affected,
                "actions": [
                    {
                        "part_id": a.part_id,
                        "action": a.action,
                        "reason": a.reason,
                        "original_bytes": a.original_bytes,
                        "pruned_bytes": a.pruned_bytes,
                    }
                    for a in s.actions
                ],
            }
            for s in result.strategies
        ],
    }


def resolve_session(db_path: Path, prefix: str) -> str:
    """Resolve a session ID prefix to a full session ID."""
    from headroom_cli.session import list_sessions

    sessions = list_sessions(db_path)
    matches = [s for s in sessions if s.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0].id
    if len(matches) > 1:
        emit_err(f"Ambiguous session prefix '{prefix}' — matches {len(matches)} sessions:")
        for m in matches[:5]:
            emit_err(f"  {m.id}  {m.title or '(untitled)'}")
        sys.exit(1)
    exact = [s for s in sessions if s.id == prefix]
    if exact:
        return exact[0].id
    emit_err(f"No session found matching '{prefix}'")
    sys.exit(1)


def ensure_strategies() -> None:
    """Import strategies module to trigger registration."""
    import headroom_cli.strategies  # noqa: F401

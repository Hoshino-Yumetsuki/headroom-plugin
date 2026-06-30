"""Guard daemon — background monitoring and auto-pruning."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from headroom_cli.config import Config, load_config
from headroom_cli.helpers import emit, emit_err, format_bytes
from headroom_cli.session import get_db_path, get_session_data, list_sessions
from headroom_cli.tokens import estimate_session_tokens


def start_guard(
    *,
    rx_name: str = "gentle",
    threshold: float = 0.80,
    interval: int = 30,
    session_id: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Start blocking guard that monitors session size and auto-prunes.

    Runs in a loop: check token usage, prune if above threshold, sleep.
    """
    # Lazy import to avoid circular dependency
    from headroom_cli.executor import run_prescription

    resolved_db = db_path or get_db_path()
    config = load_config()

    emit(f"Guard started: rx={rx_name}, threshold={threshold:.0%}, interval={interval}s")

    while True:
        try:
            sid = _resolve_session_id(resolved_db, session_id)
            if sid is None:
                emit_err("No active session found, waiting...")
                time.sleep(interval)
                continue

            messages, parts = get_session_data(resolved_db, sid)
            est_tokens = estimate_session_tokens(messages, parts)
            usage_pct = est_tokens / config.context_window

            if usage_pct > threshold:
                emit(
                    f"  [{_now_str()}] Session {sid[:8]}... "
                    f"at {usage_pct:.0%} (>{threshold:.0%}), pruning with '{rx_name}'..."
                )
                result = run_prescription(
                    resolved_db,
                    sid,
                    rx_name,
                    config,
                    dry_run=False,
                )
                emit(
                    f"  Pruned: {format_bytes(result.total_bytes_saved)} saved, "
                    f"{result.total_parts_affected} parts affected"
                )
            else:
                emit(
                    f"  [{_now_str()}] Session {sid[:8]}... "
                    f"at {usage_pct:.0%} — OK"
                )

        except FileNotFoundError:
            emit_err("Database not found, waiting...")
        except Exception as exc:
            emit_err(f"Guard error: {exc}")

        time.sleep(interval)


def start_guard_daemon(
    *,
    rx_name: str = "gentle",
    threshold: float = 0.80,
    interval: int = 30,
    session_id: str | None = None,
) -> int:
    """Fork guard into background daemon process. Returns child PID."""
    if sys.platform == "win32":
        return _start_daemon_windows(
            rx_name=rx_name,
            threshold=threshold,
            interval=interval,
            session_id=session_id,
        )
    return _start_daemon_unix(
        rx_name=rx_name,
        threshold=threshold,
        interval=interval,
        session_id=session_id,
    )


def _start_daemon_unix(
    *,
    rx_name: str,
    threshold: float,
    interval: int,
    session_id: str | None,
) -> int:
    """Fork on Unix-like systems."""
    pid = os.fork()
    if pid > 0:
        return pid
    # Child: detach
    os.setsid()
    # Close standard FDs
    sys.stdin.close()
    devnull = open(os.devnull, "w")  # noqa: SIM115
    sys.stdout = devnull
    sys.stderr = devnull
    start_guard(
        rx_name=rx_name,
        threshold=threshold,
        interval=interval,
        session_id=session_id,
    )
    return 0  # unreachable


def _start_daemon_windows(
    *,
    rx_name: str,
    threshold: float,
    interval: int,
    session_id: str | None,
) -> int:
    """Spawn detached process on Windows."""
    import subprocess

    args = [
        sys.executable,
        "-m",
        "headroom_cli",
        "guard",
        "--foreground",
        "--rx",
        rx_name,
        "--threshold",
        str(threshold),
        "--interval",
        str(interval),
    ]
    if session_id:
        args.extend(["--session", session_id])

    # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
    creation_flags = 0x00000200 | 0x00000008
    proc = subprocess.Popen(
        args,
        creationflags=creation_flags,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.pid


def _resolve_session_id(db_path: Path, session_id: str | None) -> str | None:
    """Resolve session ID — use provided or find most recent."""
    if session_id:
        return session_id
    sessions = list_sessions(db_path)
    if sessions:
        return sessions[0].id
    return None


def _now_str() -> str:
    """Current time as HH:MM:SS."""
    t = time.localtime()
    return f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"

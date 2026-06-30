"""CLI command handlers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from headroom_cli.helpers import (
    emit,
    emit_err,
    ensure_strategies,
    format_bytes,
    format_timestamp,
    prescription_to_dict,
    resolve_session,
)


def cmd_list(db_path: Path | None, args: argparse.Namespace) -> None:
    """List sessions with sizes and token estimates."""
    from headroom_cli.session import get_db_path, get_parts, list_sessions
    from headroom_cli.tokens import estimate_tokens

    resolved = db_path or get_db_path()
    sessions = list_sessions(resolved, project_id=args.project)

    if not sessions:
        emit("No sessions found.")
        return

    if args.as_json:
        rows = []
        for s in sessions:
            parts = get_parts(resolved, s.id)
            total_bytes = sum(p.byte_size for p in parts)
            est_tokens = sum(estimate_tokens(str(p.data)) for p in parts)
            rows.append({
                "id": s.id,
                "title": s.title,
                "messages": s.tokens_input + s.tokens_output,
                "total_bytes": total_bytes,
                "estimated_tokens": est_tokens,
                "updated": s.time_updated,
            })
        emit(json.dumps(rows, indent=2))
        return

    emit(f"{'ID':<12} {'Title':<30} {'Size':>10} {'Est.Tokens':>12} {'Updated'}")
    emit("-" * 80)
    for s in sessions:
        parts = get_parts(resolved, s.id)
        total_bytes = sum(p.byte_size for p in parts)
        est_tokens = sum(estimate_tokens(str(p.data)) for p in parts)
        title = s.title[:28] if s.title else "(untitled)"
        emit(
            f"{s.id[:10]:<12} {title:<30} {format_bytes(total_bytes):>10} "
            f"{est_tokens:>12,} {format_timestamp(s.time_updated)}"
        )


def cmd_diagnose(db_path: Path | None, args: argparse.Namespace) -> None:
    """Analyze bloat sources in a session."""
    from headroom_cli.diagnosis import diagnose_session
    from headroom_cli.session import get_db_path

    resolved = db_path or get_db_path()
    session_id = resolve_session(resolved, args.session)
    result = diagnose_session(resolved, session_id)

    if args.as_json:
        emit(json.dumps(result, indent=2))
        return

    emit(f"Session: {result['session_id']}")
    emit(f"Total: {format_bytes(result['total_bytes'])} | "
         f"{result['total_parts']} parts | "
         f"{result['total_messages']} messages | "
         f"~{result['estimated_tokens']:,} tokens")
    emit("")
    emit(f"{'Category':<16} {'Bytes':>12} {'Count':>8} {'%':>8}")
    emit("-" * 48)
    for cat, data in result["breakdown"].items():
        emit(
            f"{cat:<16} {format_bytes(int(data['bytes'])):>12} "
            f"{int(data['count']):>8} {float(data['pct']):>7.1f}%"
        )
    emit("")
    emit(f"Recommended: {', '.join(result['recommendations'])}")


def cmd_treat(db_path: Path | None, args: argparse.Namespace) -> None:
    """Run a prescription on a session."""
    from headroom_cli.config import load_config
    from headroom_cli.executor import run_prescription
    from headroom_cli.safety import PruneValidationError
    from headroom_cli.session import get_db_path

    resolved = db_path or get_db_path()
    session_id = resolve_session(resolved, args.session)
    config = load_config()
    dry_run = not args.execute

    ensure_strategies()

    mode = "DRY RUN" if dry_run else "EXECUTING"
    emit(f"[{mode}] Prescription: {args.rx} on session {session_id[:10]}...")
    emit("")

    try:
        result = run_prescription(
            resolved, session_id, args.rx, config, dry_run=dry_run,
        )
    except PruneValidationError as exc:
        emit_err(f"Safety floor violated: {exc}")
        sys.exit(1)

    if args.as_json:
        emit(json.dumps(prescription_to_dict(result), indent=2))
        return

    for sr in result.strategies:
        if sr.parts_affected > 0:
            emit(f"  {sr.name}: {format_bytes(sr.bytes_saved)} saved, {sr.parts_affected} parts")

    emit("")
    emit(
        f"Total: {format_bytes(result.total_bytes_saved)} saved, "
        f"{result.total_parts_affected} parts affected"
    )
    if dry_run:
        emit("")
        emit("This was a dry run. Pass --execute to apply changes.")


def cmd_strategy(db_path: Path | None, args: argparse.Namespace) -> None:
    """Run a single named strategy."""
    from headroom_cli.config import load_config
    from headroom_cli.executor import execute_actions
    from headroom_cli.registry import STRATEGIES
    from headroom_cli.session import get_db_path, get_session_data

    ensure_strategies()

    resolved = db_path or get_db_path()
    session_id = resolve_session(resolved, args.session)
    config = load_config()

    info = STRATEGIES.get(args.name)
    if info is None:
        emit_err(f"Unknown strategy: {args.name}")
        emit_err(f"Available: {', '.join(sorted(STRATEGIES))}")
        sys.exit(1)

    messages, parts = get_session_data(resolved, session_id)
    result = info.func(messages, parts, config)  # type: ignore[operator]

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTING"
    emit(f"[{mode}] Strategy: {args.name}")
    emit(f"  {format_bytes(result.bytes_saved)} saved, {result.parts_affected} parts")

    if not dry_run and result.actions:
        execute_actions(resolved, session_id, result.actions, dry_run=False)
        emit("  Applied.")

    if dry_run and result.actions:
        emit("")
        emit("This was a dry run. Pass --execute to apply changes.")


def cmd_guard(db_path: Path | None, args: argparse.Namespace) -> None:
    """Start guard daemon."""
    from headroom_cli.guard import start_guard, start_guard_daemon
    from headroom_cli.session import get_db_path

    ensure_strategies()

    if args.foreground:
        start_guard(
            rx_name=args.rx,
            threshold=args.threshold,
            interval=args.interval,
            session_id=args.session,
            db_path=db_path or get_db_path(),
        )
    else:
        pid = start_guard_daemon(
            rx_name=args.rx,
            threshold=args.threshold,
            interval=args.interval,
            session_id=args.session,
        )
        emit(f"Guard daemon started (PID {pid})")


def cmd_doctor(db_path: Path | None) -> None:
    """Health check — verify db access and show stats."""
    from headroom_cli.config import CONFIG_DIR, CONFIG_FILE, load_config
    from headroom_cli.session import get_db_path, list_sessions

    emit("headroom-cli doctor")
    emit("=" * 40)

    config = load_config()
    emit(f"Config dir:     {CONFIG_DIR}")
    emit(f"Config file:    {CONFIG_FILE} ({'exists' if CONFIG_FILE.is_file() else 'not found'})")
    emit(f"Context window: {config.context_window:,}")
    emit("")

    try:
        resolved = db_path or get_db_path()
        emit(f"Database: {resolved}")
        sessions = list_sessions(resolved)
        emit(f"Sessions: {len(sessions)}")
        if sessions:
            latest = sessions[0]
            emit(f"Latest:   {latest.id[:10]}... — {latest.title or '(untitled)'}")
            emit(f"Updated:  {format_timestamp(latest.time_updated)}")
        emit("")
        emit("Status: OK")
    except FileNotFoundError as exc:
        emit_err(f"Database: {exc}")
        emit_err("")
        emit_err("Status: FAIL — database not found")
        sys.exit(1)


def cmd_formulary() -> None:
    """Show all strategies and prescriptions."""
    from headroom_cli.registry import PRESCRIPTIONS, STRATEGIES

    ensure_strategies()

    emit("STRATEGIES")
    emit("=" * 60)
    for name in sorted(STRATEGIES):
        info = STRATEGIES[name]
        emit(f"  {name:<30} [{info.tier}] {info.expected_savings}")
        emit(f"    {info.description}")
    emit("")

    emit("PRESCRIPTIONS")
    emit("=" * 60)
    for rx_name, strats in PRESCRIPTIONS.items():
        emit(f"  {rx_name}: {len(strats)} strategies")
        for s in strats:
            marker = "*" if s in STRATEGIES else "?"
            emit(f"    {marker} {s}")
    emit("")


def cmd_init() -> None:
    """First-time setup."""
    from headroom_cli.config import CONFIG_DIR, CONFIG_FILE, ensure_config_dir

    ensure_config_dir()
    emit(f"Config directory: {CONFIG_DIR}")

    if not CONFIG_FILE.is_file():
        default_config = {
            "context_window": 200000,
            "floor": {
                "max_message_drop_pct": 0.50,
                "preserve_last_k_turns": 10,
                "preserve_first_message": True,
            },
        }
        CONFIG_FILE.write_text(
            json.dumps(default_config, indent=2) + "\n",
            encoding="utf-8",
        )
        emit(f"Created config: {CONFIG_FILE}")
    else:
        emit(f"Config exists:  {CONFIG_FILE}")

    try:
        from headroom_cli.session import get_db_path

        db = get_db_path()
        emit(f"Database found: {db}")
    except FileNotFoundError:
        emit_err("Database not found — set OPENCODE_DB or ensure OpenCode is installed")

    emit("")
    emit("Setup complete.")


def cmd_completions(args: argparse.Namespace) -> None:
    """Output shell completion script."""
    from headroom_cli._completions import bash_completions, fish_completions, zsh_completions

    match args.shell:
        case "bash":
            emit(bash_completions())
        case "zsh":
            emit(zsh_completions())
        case "fish":
            emit(fish_completions())



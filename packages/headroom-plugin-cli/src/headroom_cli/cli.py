"""CLI entry point — argparse wiring and dispatch."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from headroom_cli import __version__


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="headroom-cli",
        description="Context pruning for OpenCode sessions",
    )
    parser.add_argument(
        "--version", action="version", version=f"headroom-cli {__version__}"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to OpenCode SQLite database",
    )

    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List sessions with sizes and token estimates")
    p_list.add_argument("--project", type=str, default=None, help="Filter by project directory")
    p_list.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")

    # diagnose
    p_diag = sub.add_parser("diagnose", help="Analyze bloat sources in a session")
    p_diag.add_argument("session", type=str, help="Session ID (or prefix)")
    p_diag.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")

    # treat
    p_treat = sub.add_parser("treat", help="Run prescription (dry-run by default)")
    p_treat.add_argument("session", type=str, help="Session ID (or prefix)")
    p_treat.add_argument(
        "--rx",
        type=str,
        default="gentle",
        choices=["gentle", "standard", "aggressive"],
        help="Prescription tier (default: gentle)",
    )
    p_treat.add_argument(
        "--execute",
        action="store_true",
        help="Actually apply changes (default is dry-run)",
    )
    p_treat.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")

    # strategy
    p_strat = sub.add_parser("strategy", help="Run a single named strategy")
    p_strat.add_argument("name", type=str, help="Strategy name")
    p_strat.add_argument("session", type=str, help="Session ID (or prefix)")
    p_strat.add_argument(
        "--execute",
        action="store_true",
        help="Actually apply changes",
    )

    # guard
    p_guard = sub.add_parser("guard", help="Start background monitoring daemon")
    p_guard.add_argument(
        "--rx",
        type=str,
        default="gentle",
        choices=["gentle", "standard", "aggressive"],
    )
    p_guard.add_argument("--threshold", type=float, default=0.80, help="Usage threshold (0-1)")
    p_guard.add_argument("--interval", type=int, default=30, help="Check interval in seconds")
    p_guard.add_argument("--session", type=str, default=None, help="Session ID to monitor")
    p_guard.add_argument("--foreground", action="store_true", help="Run in foreground")

    # doctor
    sub.add_parser("doctor", help="Health check (db accessible, session stats)")

    # formulary
    sub.add_parser("formulary", help="Show all strategies and prescriptions")

    # init
    sub.add_parser("init", help="First-time setup")

    # completions
    p_comp = sub.add_parser("completions", help="Shell completion scripts")
    p_comp.add_argument("shell", type=str, choices=["bash", "zsh", "fish"])

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    db_path: Path | None = Path(args.db) if args.db else None

    # Lazy import to keep cli.py thin
    from headroom_cli.commands import (
        cmd_completions,
        cmd_diagnose,
        cmd_doctor,
        cmd_formulary,
        cmd_guard,
        cmd_init,
        cmd_list,
        cmd_strategy,
        cmd_treat,
    )

    match args.command:
        case "list":
            cmd_list(db_path, args)
        case "diagnose":
            cmd_diagnose(db_path, args)
        case "treat":
            cmd_treat(db_path, args)
        case "strategy":
            cmd_strategy(db_path, args)
        case "guard":
            cmd_guard(db_path, args)
        case "doctor":
            cmd_doctor(db_path)
        case "formulary":
            cmd_formulary()
        case "init":
            cmd_init()
        case "completions":
            cmd_completions(args)
        case _:
            parser.print_help()

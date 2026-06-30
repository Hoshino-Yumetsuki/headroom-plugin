"""CLI entry point — argparse wiring and dispatch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from headroom_cli import __version__


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="headroom-cli",
        description="Generic context compression backend (client-agnostic)",
    )
    parser.add_argument(
        "--version", action="version", version=f"headroom-cli {__version__}"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="[OpenCode adapter] Path to OpenCode SQLite database",
    )

    sub = parser.add_subparsers(dest="command")

    # compress (generic API - stdin/stdout)
    p_compress = sub.add_parser("compress", help="Compress session via JSON stdin/stdout")
    p_compress.add_argument(
        "--rx",
        type=str,
        default="gentle",
        choices=["gentle", "standard", "aggressive"],
        help="Prescription tier (default: gentle)",
    )

    # diagnose (generic API - stdin/stdout)
    sub.add_parser("diagnose", help="Diagnose bloat via JSON stdin/stdout")

    # --- OpenCode-specific commands (require --db) ---

    # list
    p_list = sub.add_parser("list", help="[OpenCode] List sessions with sizes and token estimates")
    p_list.add_argument("--project", type=str, default=None, help="Filter by project directory")
    p_list.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")

    # treat
    p_treat = sub.add_parser("treat", help="[OpenCode] Run prescription (dry-run by default)")
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
    p_strat = sub.add_parser("strategy", help="[OpenCode] Run a single named strategy")
    p_strat.add_argument("name", type=str, help="Strategy name")
    p_strat.add_argument("session", type=str, help="Session ID (or prefix)")
    p_strat.add_argument(
        "--execute",
        action="store_true",
        help="Actually apply changes",
    )

    # guard
    p_guard = sub.add_parser("guard", help="[OpenCode] Start background monitoring daemon")
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
    sub.add_parser("doctor", help="[OpenCode] Health check (db accessible, session stats)")

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

    # Generic API commands (stdin/stdout)
    if args.command in ("compress", "diagnose"):
        from headroom_cli.api import compress, diagnose

        try:
            # Read JSON from stdin
            request = json.load(sys.stdin)

            # Dispatch to generic API
            if args.command == "compress":
                if hasattr(args, "rx"):
                    request["prescription"] = args.rx
                response = compress(request)
            else:  # diagnose
                response = diagnose(request)

            # Write JSON to stdout
            json.dump(response, sys.stdout, indent=2)
            sys.stdout.write("\n")
            sys.exit(0 if response["status"] == "success" else 1)

        except json.JSONDecodeError as e:
            error_response = {
                "status": "error",
                "error": "Invalid JSON input",
                "details": str(e),
            }
            json.dump(error_response, sys.stdout, indent=2)
            sys.stdout.write("\n")
            sys.exit(1)
        except Exception as e:
            error_response = {
                "status": "error",
                "error": str(e),
                "details": type(e).__name__,
            }
            json.dump(error_response, sys.stdout, indent=2)
            sys.stdout.write("\n")
            sys.exit(1)

    # OpenCode-specific commands (require --db)
    db_path: Path | None = Path(args.db) if args.db else None

    # Lazy import to keep cli.py thin
    from headroom_cli.commands import (
        cmd_completions,
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

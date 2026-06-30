"""CLI entry point — argparse wiring and dispatch."""
from __future__ import annotations

import argparse
import json
import sys

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

    parser.print_help()
    sys.exit(1)

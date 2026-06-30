"""CLI entry point for headroom-plugin-cli."""

from __future__ import annotations

import json
import sys

from headroom_cli.api import compress


def main() -> None:
    """Main CLI entry point. Reads JSON from stdin, outputs JSON to stdout."""
    try:
        # Read request from stdin
        request = json.load(sys.stdin)
        
        # Process compression
        response = compress(request)
        
        # Output response to stdout
        json.dump(response, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        
    except json.JSONDecodeError as e:
        error_response = {
            "status": "error",
            "error": "Invalid JSON input",
            "error_type": "JSONDecodeError",
            "details": str(e),
        }
        json.dump(error_response, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)
        
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }
        json.dump(error_response, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

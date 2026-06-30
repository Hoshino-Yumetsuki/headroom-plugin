"""CLI entry point for headroom-plugin-cli."""

from __future__ import annotations

import argparse
import json
import sys

from headroom_cli.api import compress


def main() -> None:
    """Main CLI entry point. Supports both stdin/stdout and file I/O."""
    parser = argparse.ArgumentParser(description='Headroom compression CLI')
    parser.add_argument('--input', help='Input JSON file path')
    parser.add_argument('--output', help='Output JSON file path')
    args = parser.parse_args()
    
    try:
        # Read input
        if args.input:
            with open(args.input, 'r', encoding='utf-8') as f:
                request = json.load(f)
        else:
            # Fallback to stdin
            request = json.load(sys.stdin)
        
        # Process compression
        response = compress(request)
        
        # Write output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(response, f, indent=2, ensure_ascii=False)
        else:
            # Fallback to stdout
            json.dump(response, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        
    except json.JSONDecodeError as e:
        error_response = {
            "status": "error",
            "error": "Invalid JSON input",
            "error_type": "JSONDecodeError",
            "details": str(e),
        }
        _write_error(error_response, args.output)
        sys.exit(1)
        
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }
        _write_error(error_response, args.output)
        sys.exit(1)


def _write_error(error_response: dict, output_file: str | None) -> None:
    """Write error response to file or stdout."""
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(error_response, f, indent=2)
    else:
        json.dump(error_response, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()

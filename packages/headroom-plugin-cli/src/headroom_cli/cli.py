"""CLI entry point for headroom-plugin-cli."""

from __future__ import annotations

import json
import sys
import io

from headroom_cli.api import compress


def main() -> None:
    """Main CLI entry point. Reads JSON from stdin, outputs JSON to stdout."""
    # Force UTF-8 encoding for stdout/stderr on Windows
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)
    
    try:
        # Read from stdin with explicit binary mode to avoid Windows encoding issues
        if hasattr(sys.stdin, 'buffer'):
            # Binary mode available - read raw bytes
            stdin_bytes = sys.stdin.buffer.read()
            stdin_text = stdin_bytes.decode('utf-8')
            request = json.loads(stdin_text)
        else:
            # Fallback to text mode
            request = json.load(sys.stdin)
        
        # Process compression
        response = compress(request)
        
        # Output response to stdout (now UTF-8 encoded)
        json.dump(response, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        
    except json.JSONDecodeError as e:
        error_response = {
            "status": "error",
            "error": "Invalid JSON input",
            "error_type": "JSONDecodeError",
            "details": str(e),
        }
        json.dump(error_response, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.exit(1)
        
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }
        json.dump(error_response, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()

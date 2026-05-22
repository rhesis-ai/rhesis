"""Entry point for running Polymath as a module.

Usage:
    python -m polymath
    python -m polymath --host 0.0.0.0 --port 8889
"""

from __future__ import annotations

import sys


def main() -> None:
    """Run the Polymath FastAPI server."""
    import uvicorn

    host = "0.0.0.0"
    port = 8889

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        else:
            i += 1

    uvicorn.run(
        "polymath.app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()

"""Entry point for running the Travel Agent FastAPI dev server.

Usage:
    python -m travel_agent
    python -m travel_agent --host 0.0.0.0 --port 8890
    python -m travel_agent --no-reload

This starts a local development server (auto-reload on by default). It is not
meant for production use.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m travel_agent",
        description="Run the Travel Agent FastAPI development server.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host interface to bind. Defaults to 0.0.0.0.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8890,
        help="Port to listen on. Defaults to 8890.",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable auto-reload (enabled by default for local development).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the Travel Agent FastAPI server."""
    import uvicorn

    args = _build_parser().parse_args(argv)
    uvicorn.run(
        "travel_agent.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

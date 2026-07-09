"""Entry point for running the Dr-Rhesis FastAPI dev server."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dr_rhesis",
        description="Run the Dr-Rhesis FastAPI development server.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8891)
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable auto-reload (enabled by default).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    import uvicorn

    args = _build_parser().parse_args(argv)
    uvicorn.run(
        "dr_rhesis.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

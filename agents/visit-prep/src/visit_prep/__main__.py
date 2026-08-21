"""Entry point for running the Visit-Prep FastAPI dev server."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

# Each integration has its own app module; this only selects which one uvicorn imports.
APP_MODULES = {
    "native": "visit_prep.app:app",
    "upstream": "visit_prep.app_upstream:app",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m visit_prep",
        description="Run the Visit-Prep FastAPI development server.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8891)
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable auto-reload (enabled by default).",
    )
    parser.add_argument(
        "--tracing",
        choices=sorted(APP_MODULES),
        default="native",
        help=(
            "Which Haystack tracing integration to serve through: 'native' for "
            "rhesis-sdk[haystack] (default), 'upstream' for the rhesis-haystack package."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    import uvicorn

    args = _build_parser().parse_args(argv)
    uvicorn.run(
        APP_MODULES[args.tracing],
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

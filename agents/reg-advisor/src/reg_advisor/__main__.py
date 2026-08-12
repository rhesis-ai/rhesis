"""Entry point for running the Reg-Advisor FastAPI dev server."""

from __future__ import annotations

import argparse

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8892


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m reg_advisor",
        description="Run the Reg-Advisor dev server.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default: {DEFAULT_PORT}")
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="disable auto-reload",
    )
    args = parser.parse_args()

    import uvicorn

    # The app is passed as an import string so --reload can re-import it.
    uvicorn.run(
        "reg_advisor.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

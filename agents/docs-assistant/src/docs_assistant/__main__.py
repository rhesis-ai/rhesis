"""Entry point for running the Docs Assistant dev server."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

DEFAULT_HOST = "0.0.0.0"
# 8890-8892 are taken by travel-agent, visit-prep and reg-advisor.
DEFAULT_PORT = 8893


def main() -> None:
    load_dotenv()
    port = int(os.getenv("DOCS_ASSISTANT_PORT") or DEFAULT_PORT)
    parser = argparse.ArgumentParser(
        prog="python -m docs_assistant",
        description="Run the Docs Assistant dev server.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=port, help=f"default: {port}")
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
        "docs_assistant.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

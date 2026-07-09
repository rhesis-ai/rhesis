"""Keep a persistent Rhesis connector open for the playground (stub).

Haystack SDK integration is not on main yet, so this script documents the
intended serving boundary but does not register a live connector.
"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dr_rhesis.examples.serve_playground")


def main() -> int:
    load_dotenv()
    logger.error(
        "serve_playground is a stub until rhesis-sdk Haystack auto_instrument "
        "lands on main. Use examples/chat_cli.py or POST /chat via "
        "python -m dr_rhesis instead."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

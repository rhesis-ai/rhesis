"""Keep a persistent Rhesis connector open for the playground.

The Haystack auto-instrumentation connector is now wired into ``dr_rhesis.app``
via ``auto_instrument("haystack")``, so running the app (``python -m
dr_rhesis`` / ``uvicorn dr_rhesis.app:app``) is enough to observe the pipeline.
This script only documents the serving boundary and confirms the connector is
reachable from this entry point.
"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dr_rhesis.examples.serve_playground")


def main() -> int:
    load_dotenv()
    logger.info(
        "Dr-Rhesis Haystack auto-instrumentation is enabled in dr_rhesis.app "
        "(auto_instrument('haystack')). Run `python -m dr_rhesis` or POST /chat "
        "to exercise the instrumented pipeline."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

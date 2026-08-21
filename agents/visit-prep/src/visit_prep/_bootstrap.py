"""Environment setup that has to happen before Haystack is imported.

Haystack reads ``HAYSTACK_CONTENT_TRACING_ENABLED`` once, in ``ProxyTracer.__init__``, when
``haystack.tracing`` builds its module-level tracer. Setting the flag after that point is silently
ignored and every span arrives with no prompts or completions.

``visit_prep/__init__.py`` imports the pipeline, which imports Haystack, so an app module cannot set
the flag early enough -- the parent package has already run. This is called at the top of that
``__init__``, which is the earliest point any import of ``visit_prep`` passes through.
"""

from __future__ import annotations

import os
from pathlib import Path

# src/visit_prep/_bootstrap.py -> the project root that holds .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def bootstrap() -> None:
    """Load ``.env``, then default Haystack content tracing on.

    In that order, so an explicit ``HAYSTACK_CONTENT_TRACING_ENABLED=false`` in ``.env`` is
    honoured rather than overridden by the default.
    """
    from dotenv import load_dotenv

    # The explicit path covers the documented editable checkout; the fallback searches upward from
    # the working directory, which is what a non-editable install needs.
    if not load_dotenv(PROJECT_ROOT / ".env"):
        load_dotenv()

    os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")

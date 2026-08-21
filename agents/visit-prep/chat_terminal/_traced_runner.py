"""Shared harness for the traced chat entry points.

The two traced variants — ``chat_traced_native.py`` and ``chat_traced_upstream.py`` — differ only
in which ``RhesisTracing`` class they import. Everything else about running a traced REPL lives
here, so the integrations stay separated without the harness drifting between them.

This module imports nothing from Haystack or either integration, which is what lets a variant
import it *before* choosing an integration and still control import ordering.
"""

from __future__ import annotations

import atexit
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Protocol

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHAT_DIR = Path(__file__).resolve().parent
TURN_SPAN_NAME = "function.visit_prep_turn"


class TracingFactory(Protocol):
    """The slice of ``RhesisTracing`` this harness needs. Both integrations satisfy it."""

    def __call__(self, name: str, *, turn_span_name: str = ...) -> Any: ...


def bootstrap() -> None:
    """Load ``.env`` and switch Haystack content tracing on.

    Call this before importing an integration. Haystack reads
    ``HAYSTACK_CONTENT_TRACING_ENABLED`` once, when it is imported, and the upstream integration
    imports Haystack at module level — so setting it afterwards would silently produce spans with
    no prompts or completions.
    """
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")


def run_traced_chat(tracing_cls: TracingFactory, *, label: str) -> int:
    """Run the REPL with each turn wrapped in a Rhesis turn span.

    One trace conversation per launch: a ``reset`` in the REPL starts a new agent conversation but
    stays in the same trace session.

    :param tracing_cls: The ``RhesisTracing`` class of the integration to trace through.
    :param label: Integration name, used only in the not-configured error message.
    """
    tracing = tracing_cls("Visit-Prep", turn_span_name=TURN_SPAN_NAME)
    if not tracing.enabled:
        print(
            f"Rhesis tracing ({label}) is not configured. Set RHESIS_API_KEY in "
            f"{PROJECT_ROOT / '.env'} (see .env.example).",
            file=sys.stderr,
        )
        return 1

    tracing.start_conversation(str(uuid.uuid4()))
    atexit.register(tracing.flush)

    if str(CHAT_DIR) not in sys.path:
        sys.path.insert(0, str(CHAT_DIR))

    from chat import main

    # Each turn gets its own root span, so the conversation view shows the message and the reply
    # rather than the Haystack pipeline's raw input/output dicts.
    return main(turn_hook=tracing.turn)

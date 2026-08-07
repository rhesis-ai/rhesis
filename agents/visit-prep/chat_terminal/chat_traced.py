"""Terminal chat REPL with Rhesis Haystack tracing enabled.

One trace conversation per launch: a ``reset`` in the REPL starts a new agent
conversation but stays in the same trace session.

Run from the visit-prep project root:

    cd agents/visit-prep
    uv run python chat_terminal/chat_traced.py
"""

from __future__ import annotations

import atexit
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Must precede any Haystack import so span input/output content is captured.
os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")

from haystack_integrations.tracing.rhesis import RhesisTracing  # noqa: E402

tracing = RhesisTracing("Visit-Prep", turn_span_name="function.visit_prep_turn")
if not tracing.enabled:
    print(
        f"Rhesis tracing is not configured. Set RHESIS_API_KEY in {PROJECT_ROOT / '.env'} "
        "(see .env.example).",
        file=sys.stderr,
    )
    sys.exit(1)

tracing.start_conversation(str(uuid.uuid4()))
atexit.register(tracing.flush)

_CHAT_DIR = Path(__file__).resolve().parent
if str(_CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(_CHAT_DIR))

from chat import main  # noqa: E402

if __name__ == "__main__":
    # Each turn gets its own root span, so the conversation view shows the message and the
    # reply rather than the Haystack pipeline's raw input/output dicts.
    sys.exit(main(turn_hook=tracing.turn))

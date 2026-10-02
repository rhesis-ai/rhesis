"""Terminal chat REPL with Rhesis tracing on.

The same REPL as ``chat.py``, with the Rhesis client installed and the Agents SDK spans routed
to Rhesis, so every turn (triage, the answer agent's model and tool calls, grounding, the
critic and the route decision) lands as one trace. Turns group by the REPL's conversation id;
``reset`` starts a new conversation.

Needs ``RHESIS_API_KEY`` and ``RHESIS_PROJECT_ID`` (and ``RHESIS_BASE_URL`` for a local stack)
on top of the model key. Run from the project root:

    uv run python chat_terminal/chat_traced.py
"""

from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rhesis.sdk import RhesisClient  # noqa: E402
from rhesis.telemetry.provider import shutdown_tracer_provider  # noqa: E402

from docs_assistant import tracing  # noqa: E402

if not (os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID")):
    print(
        f"Rhesis tracing is not configured. Set RHESIS_API_KEY and RHESIS_PROJECT_ID in "
        f"{PROJECT_ROOT / '.env'} (see .env.example), or use chat.py for an untraced REPL.",
        file=sys.stderr,
    )
    sys.exit(1)

# The client installs the tracer provider the bridge writes to, so it comes first.
RhesisClient.from_environment()
tracing.install()

# A REPL exits on the user's word, so the last turn's batch is flushed on the way out.
atexit.register(shutdown_tracer_provider)

_CHAT_DIR = Path(__file__).resolve().parent
if str(_CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(_CHAT_DIR))

from chat import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

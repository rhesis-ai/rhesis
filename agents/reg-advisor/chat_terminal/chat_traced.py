"""Terminal chat REPL with Rhesis tracing enabled.

The same REPL as ``chat.py``, with the Rhesis client installed and the Google ADK
integration turned on, so every agent activation, model call and tool call in
each turn is shipped to Rhesis as a trace. Turns group into a conversation by the
REPL's own conversation id; a ``reset`` starts a new one.

Needs ``RHESIS_API_KEY`` and ``RHESIS_PROJECT_ID`` on top of the Gemini key that
``chat.py`` already needs. Run from the project root:

    cd agents/reg-advisor
    uv run python chat_terminal/chat_traced.py
"""

from __future__ import annotations

import atexit
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\] feature .*", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rhesis.sdk import RhesisClient  # noqa: E402
from rhesis.sdk.telemetry import auto_instrument  # noqa: E402
from rhesis.telemetry.provider import shutdown_tracer_provider  # noqa: E402

if not (os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID")):
    print(
        f"Rhesis tracing is not configured. Set RHESIS_API_KEY and RHESIS_PROJECT_ID in "
        f"{PROJECT_ROOT / '.env'} (see .env.example), or use chat.py for an untraced REPL.",
        file=sys.stderr,
    )
    sys.exit(1)

# The client installs the tracer provider whose exporter the integration wraps,
# so it has to come first. Without it there is nothing to wrap and
# auto_instrument reports nothing enabled.
RhesisClient.from_environment()

_instrumented = auto_instrument("google_adk")
if "google_adk" not in _instrumented:
    print(
        "The Google ADK integration did not enable; traces would not be translated. "
        f"auto_instrument returned {_instrumented}.",
        file=sys.stderr,
    )
    sys.exit(1)

# A REPL exits on the user's word, so the last turn's batch has to be flushed on
# the way out or it never leaves the process.
atexit.register(shutdown_tracer_provider)

_CHAT_DIR = Path(__file__).resolve().parent
if str(_CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(_CHAT_DIR))

from chat import main  # noqa: E402

if __name__ == "__main__":
    # ``chat.py`` already threads a conversation id through every turn, and
    # session.py marks it for the integration, so each turn lands as its own
    # conversation turn root with no extra wiring here.
    sys.exit(main())

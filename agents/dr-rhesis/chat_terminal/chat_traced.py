"""Terminal chat REPL with Rhesis Haystack tracing enabled.

One trace conversation per launch: a ``reset`` in the REPL starts a new agent
conversation but stays in the same trace session.

Run from the dr-rhesis project root:

    cd agents/dr-rhesis
    uv run python chat_terminal/chat_traced.py
"""

from __future__ import annotations

import atexit
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from dr_rhesis.tracing import (  # noqa: E402
    enable_rhesis_tracing,
    flush_rhesis_tracing,
    set_trace_session,
)

if not enable_rhesis_tracing():
    print(
        "Rhesis tracing is not configured. Set RHESIS_API_KEY and "
        f"RHESIS_PROJECT_ID in {PROJECT_ROOT / '.env'} (see .env.example).",
        file=sys.stderr,
    )
    sys.exit(1)

set_trace_session(str(uuid.uuid4()))
atexit.register(flush_rhesis_tracing)

_CHAT_DIR = Path(__file__).resolve().parent
if str(_CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(_CHAT_DIR))

from chat import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

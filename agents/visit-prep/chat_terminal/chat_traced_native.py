"""Terminal chat REPL traced through the native integration in this repo.

Uses ``rhesis-sdk[haystack]`` — ``rhesis.sdk.telemetry.integrations.haystack``.

Run from the visit-prep project root:

    cd agents/visit-prep
    uv run python chat_terminal/chat_traced_native.py

For the upstream ``rhesis-haystack`` package, use ``chat_traced_upstream.py`` instead.
"""

from __future__ import annotations

import sys

from _traced_runner import bootstrap, run_traced_chat

bootstrap()

from rhesis.sdk.telemetry.integrations.haystack import RhesisTracing  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_traced_chat(RhesisTracing, label="native"))

"""Terminal chat REPL traced through deepset's upstream integration.

Uses ``rhesis-haystack`` — ``haystack_integrations.tracing.rhesis``. That package is not a
declared dependency of visit-prep, because its path source cannot be resolved from every checkout.
Install it into this project's environment first:

    cd agents/visit-prep
    uv pip install -e <path-to>/haystack-core-integrations/integrations/rhesis

Then run:

    uv run python chat_terminal/chat_traced_upstream.py

For the native integration that ships in this repo, use ``chat_traced_native.py`` instead.
"""

from __future__ import annotations

import sys

from _traced_runner import bootstrap, run_traced_chat

bootstrap()

try:
    from haystack_integrations.tracing.rhesis import RhesisTracing
except ImportError as exc:  # noqa: BLE001 - the fix is an install, so say so plainly
    raise SystemExit(
        "rhesis-haystack is not installed. Install it with:\n"
        "  uv pip install -e <path-to>/haystack-core-integrations/integrations/rhesis\n"
        "Or trace through the native integration with chat_traced_native.py."
    ) from exc

if __name__ == "__main__":
    sys.exit(run_traced_chat(RhesisTracing, label="upstream"))

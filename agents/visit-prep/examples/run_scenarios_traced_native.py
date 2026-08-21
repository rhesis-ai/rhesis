"""Run the canned scenarios traced through the native integration in this repo.

Uses ``rhesis-sdk[haystack]`` — ``rhesis.sdk.telemetry.integrations.haystack``.

Run from the visit-prep project root:

    cd agents/visit-prep
    uv run python examples/run_scenarios_traced_native.py

For the upstream ``rhesis-haystack`` package, use ``run_scenarios_traced_upstream.py`` instead.
"""

from __future__ import annotations

import sys

from _traced_runner import bootstrap, run_traced_scenarios

bootstrap()

from rhesis.sdk.telemetry.integrations.haystack import RhesisTracing  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_traced_scenarios(RhesisTracing, label="native"))

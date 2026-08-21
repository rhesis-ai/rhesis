"""Visit-Prep FastAPI application, traced through the native integration in this repo.

Uses ``rhesis-sdk[haystack]`` — ``rhesis.sdk.telemetry.integrations.haystack``. The app itself is
built by :func:`visit_prep.app_factory.create_app`; this module only picks the integration, so the
two tracing paths never share a file.

For deepset's upstream ``rhesis-haystack`` package, see ``app_upstream.py``.
"""

from __future__ import annotations  # noqa: I001 - content tracing must be set before haystack

import os

# Must precede any Haystack import so span input/output content is captured.
os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")

from rhesis.sdk.telemetry.integrations.haystack import RhesisTracing  # noqa: E402
from visit_prep.app_factory import create_app  # noqa: E402

app = create_app(RhesisTracing)

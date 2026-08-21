"""Visit-Prep FastAPI application, traced through the native integration in this repo.

Uses ``rhesis-sdk[haystack]`` — ``rhesis.sdk.telemetry.integrations.haystack``. The app itself is
built by :func:`visit_prep.app_factory.create_app`; this module only picks the integration, so the
two tracing paths never share a file.

Haystack's content-tracing flag cannot be set here: importing this module runs the package
``__init__`` first, which already imports Haystack. :mod:`visit_prep._bootstrap` owns it instead.

For deepset's upstream ``rhesis-haystack`` package, see ``app_upstream.py``.
"""

from __future__ import annotations

from rhesis.sdk.telemetry.integrations.haystack import RhesisTracing
from visit_prep.app_factory import create_app

app = create_app(RhesisTracing)

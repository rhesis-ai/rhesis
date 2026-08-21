"""Visit-Prep FastAPI application, traced through deepset's upstream integration.

Uses ``rhesis-haystack`` — ``haystack_integrations.tracing.rhesis``. That package is not a declared
dependency of visit-prep, because its path source cannot be resolved from every checkout. Install
it into this project's environment first:

    cd agents/visit-prep
    uv pip install -e <path-to>/haystack-core-integrations/integrations/rhesis

Then run the server against it:

    uv run python -m visit_prep --tracing upstream

Haystack's content-tracing flag cannot be set here: importing this module runs the package
``__init__`` first, which already imports Haystack. :mod:`visit_prep._bootstrap` owns it instead.

For the native integration that ships in this repo, see ``app.py``.
"""

from __future__ import annotations

try:
    from haystack_integrations.tracing.rhesis import RhesisTracing
except ImportError as exc:  # noqa: BLE001 - the fix is an install, so say so plainly
    raise ImportError(
        "rhesis-haystack is not installed. Install it with:\n"
        "  uv pip install -e <path-to>/haystack-core-integrations/integrations/rhesis\n"
        "Or serve the native integration with: python -m visit_prep --tracing native"
    ) from exc

from visit_prep.app_factory import create_app  # noqa: E402

app = create_app(RhesisTracing)

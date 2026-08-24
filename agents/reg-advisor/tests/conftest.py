"""Shared pytest fixtures.

Holds no fixtures on purpose: it exists so `tests.mocks` is importable and collectable, and
tests import from it directly.
"""

from __future__ import annotations

import os

# Keep the suite hermetic. This agent's .env holds real Rhesis credentials, and app.py builds a
# live RhesisClient -- which now dials the connector from its lifespan -- whenever both are set.
# TestClient runs that lifespan, so without this the tests would open a WebSocket to the platform
# and register an endpoint. Empty strings survive load_dotenv(), which does not override values
# already present in the environment.
os.environ["RHESIS_API_KEY"] = ""
os.environ["RHESIS_PROJECT_ID"] = ""

from tests.mocks import MockLlm, build_runner_with, make_runner  # noqa: E402

__all__ = ["MockLlm", "build_runner_with", "make_runner"]

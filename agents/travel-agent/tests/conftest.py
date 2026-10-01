"""Makes ``tests.mocks`` importable from the test modules.

Deliberately holds no fixtures: the scripted client is constructed per test, because each
test's script is the point of the test.
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
# The app builds its Gemini client at startup and refuses to without a key. Tests never call
# Gemini, so a placeholder is enough, and it keeps a real key from .env out of the suite.
os.environ["GOOGLE_API_KEY"] = "test-placeholder"
os.environ.pop("GEMINI_API_KEY", None)

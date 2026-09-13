"""Session setup for the backend benchmarks.

Reuses the test suite's container bootstrap (ephemeral Postgres + Redis, env
vars, Alembic at head, one org/user/token) but none of its per-test fixtures.
Results accumulate in one dict and are written to ``results/<label>.json`` at
the end of the session; ``BENCH_LABEL`` names the file, defaulting to the git
short SHA.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

import pytest

# Importing the backend conftest starts the containers and sets the env vars
# before any app module is imported. Only its helpers are used from here.
from tests.backend.conftest import _run_migrations
from tests.backend.fixtures.auth import get_or_create_session_auth

RESULTS_DIR = Path(__file__).parent / "results"


def _git_short_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except Exception:
        return "unknown"


@pytest.fixture(scope="session")
def bench_auth() -> tuple[str, str, str]:
    """(organization_id, user_id, api_token) on a migrated database."""
    _run_migrations()
    return get_or_create_session_auth()


@pytest.fixture(scope="session")
def results() -> dict:
    data: dict = {
        "label": os.environ.get("BENCH_LABEL") or _git_short_sha(),
        "git_sha": _git_short_sha(),
        "python": platform.python_version(),
        "db_latency_ms": float(os.environ.get("BENCH_DB_LATENCY_MS", "0")),
        "scenarios": {},
    }
    yield data
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{data['label']}.json"
    out.write_text(json.dumps(data, indent=2, sort_keys=True, default=str))
    print(f"\nbenchmark results written to {out}")

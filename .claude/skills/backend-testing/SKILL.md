---
name: backend-testing
description: Run the backend test suite correctly — working directory, Docker requirement, single-test vs full-suite commands. Use when running or writing backend tests in apps/backend.
---

# Backend Testing

**Ask the user before running the whole backend suite.** It takes a very long time. Default to
the narrowest selection that covers the change (single test, class, or file); only run
`../../tests/backend/` in full once the user says to.

Backend tests must run from `apps/backend` — its `pyproject.toml` sets
`testpaths = ["../../tests/backend"]` and `pythonpath = ["src"]`, so paths/imports only resolve
from that directory. Never run `uv run pytest tests/backend/...` from the repo root.

```bash
cd apps/backend
uv run pytest ../../tests/backend/ -v
# single test class:
uv run pytest ../../tests/backend/services/explorer/test_tests.py::TestCreateExplorerTestSet -v
```

Backend tests need Docker running — `tests/backend/conftest.py` starts an ephemeral Postgres and
Redis container per pytest-xdist worker via Testcontainers (see
`tests/backend/testcontainers_setup.py`), no manual setup needed. If tests fail with connection or
container errors, stop and ask the user to start Docker instead of trying to work around it or
debug the test code.

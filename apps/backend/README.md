# Rhesis Backend

FastAPI service for evaluations, test execution, models, and related APIs. Python **3.12+**; dependencies and tooling are managed with [uv](https://docs.astral.sh/uv/) (`requires-python` is set in `pyproject.toml`).

## Setup

From `apps/backend`:

```bash
uv sync --dev
source .venv/bin/activate
```

The SDK is pulled in as an editable path dependency via `pyproject.toml`; no extra `pip install` steps.

## Run

- **Repository root:** `./rh dev backend`
- **This directory:** `./start.sh`
- **Direct:** `uv run uvicorn rhesis.backend.app.main:app --host 0.0.0.0 --port 8080 --reload --log-level debug`

> **Note:** Docker Desktop must be running. `./rh dev up` and `make test` both rely on Docker Compose to start Postgres and Redis.

## Database

The API expects **PostgreSQL**. **Redis** is used for caching and Celery-backed work (start a worker with `./rh dev worker` from the repository root when you need background jobs).

For local development, bring up Postgres and Redis from the repository root (`./rh dev init` once, then `./rh dev up`) and ensure `apps/backend/.env` points at that instance. Apply the schema from `apps/backend/src/rhesis/backend` with:

```bash
uv run alembic upgrade head
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for linting, formatting, type checking, and running tests.

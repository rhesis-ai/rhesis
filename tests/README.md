# Tests

Every test suite in the monorepo lives under `tests/`, never next to source. Each suite runs from
its own project directory: that's where `uv run` finds the environment with the package installed
editable, so `import rhesis.backend...` resolves. From the repo root it doesn't.

## Layout

| Directory | Suite | Run from |
| --- | --- | --- |
| `backend/` | FastAPI backend, incl. `ee/` | `apps/backend` |
| `notifications/` | Email templates and onboarding mails | `apps/backend` |
| `sdk/` | Python SDK | `sdk` |
| `penelope/` | Penelope testing agent | `penelope` |
| `polyphemus/` | Polyphemus service | `apps/polyphemus` |
| `release_tools/` | Release scripts in `.github/release_tools/` | any env with pytest |
| `k6/` | Load tests against deployed environments | `tests/k6` |
| `frontend/` | Holds only a README — see [Frontend](#frontend) | — |

`pytest.ini` at this level declares the shared markers, `conftest.py` a few fixtures. The
two compose files here provide backing services: `docker-compose.test.yml` for the SDK integration
suite, `docker-compose.frontend.yml` for the frontend E2E suite.

## Running

### Backend

Run from `apps/backend`. A bare `uv run pytest` there picks up its `pyproject.toml` as the
configfile, whose `testpaths` covers both `../../tests/backend` and `../../tests/notifications`.
Pass an explicit path and pytest uses `tests/pytest.ini` instead — same markers, but its
`addopts` and `pythonpath` are dropped, since only the winning configfile's settings apply. This is
what CI and `make test` do.

```bash
cd apps/backend
uv sync --extra all --extra ee  # once per checkout: rhesis-sdk is behind `all`, rhesis.backend.ee behind `ee`
uv run pytest ../../tests/backend/services/explorer/test_tests.py -v
make test                       # full suite: xdist, 120s timeout, one rerun on failure
make test-lf                    # re-run last failures
```

Docker must be running. `tests/backend/conftest.py` starts an ephemeral Postgres and Redis per
pytest-xdist worker via [Testcontainers](https://testcontainers.com/) on random host ports (see
`tests/backend/testcontainers_setup.py`). No compose file or manual setup.

The full suite takes a long time — prefer the narrowest selection that covers your change. See the
`backend-testing` skill for details.

### SDK

```bash
cd sdk
make test              # unit tests, skips tests/sdk/integration
make test-integration  # starts the compose stack, then runs everything
make docker-down       # stop the stack (docker-clean also drops volumes)

# backend logs from an integration run:
docker compose -f ../tests/docker-compose.test.yml --profile sdk logs sdk-test-backend
```

Integration tests need Docker. The `sdk` profile in `docker-compose.test.yml` exposes PostgreSQL on
10001, Redis on 10002 and the backend on 10003.

### Frontend

Frontend tests are the exception to the `tests/` rule: Jest unit tests sit next to the code they
cover, under `apps/frontend/src/**/__tests__/` and `ee/frontend/src/**/__tests__/`. Playwright E2E
specs live in `apps/frontend/tests/e2e/`. `tests/frontend/` holds a README only.

```bash
cd apps/frontend
npm test               # Jest
npm run test:ci        # Jest with coverage, as CI runs it
make test-e2e          # @sanity + @crud against a Docker backend on 14003
make test-e2e-smoke    # @sanity only
make test-e2e-local    # @mocked, against a local mock backend — no Docker
make docker-down
```

Playwright specs are selected by tag, and the Make targets above pick which tags run. See
[`frontend/README.md`](./frontend/README.md) for the tag-to-project mapping.

### Other suites

```bash
cd penelope && make test          # or: uv run pytest
cd apps/polyphemus && uv run pytest
```

`release_tools/` has no Make target or CI workflow of its own. It needs any environment with pytest
— `apps/backend`'s works — and its `conftest.py` puts `.github` on `sys.path` so imports resolve
the way `python3 .github/release` does:

```bash
cd apps/backend && uv run pytest ../../tests/release_tools
```

k6 load tests run against `api.rhesis.ai` and `app.rhesis.ai`, not a local stack — see
[`k6/README.md`](./k6/README.md) for the scenarios, required env vars and safety thresholds.

## Markers

Declared in `tests/pytest.ini`; `apps/backend/pyproject.toml` repeats the same set. Five markers:

- Scope: `unit`, `integration`, `slow`
- Other: `security`, `ee` (needs `rhesis-backend-ee` installed)

Nothing selects on them — no CI job, Makefile target or fixture reads a marker. They exist so `-m`
is available if a suite grows into needing it. Note that roughly half of backend tests carry no
marker at all, so `-m unit` runs well short of the whole fast suite.

There are no area markers: select a directory by path instead of by marker, e.g.
`../../tests/backend/crud/` rather than `-m crud`.

```bash
uv run pytest ../../tests/backend -m unit
uv run pytest ../../tests/backend -m "integration and not slow"
```

## Naming

- Python test files: `test_<module>.py`; classes `Test<Thing>`; methods
  `test_<functionality>_<condition>_<expected_result>`.
- Frontend: `<ComponentName>.test.tsx` for Jest, `<feature>.spec.ts` for Playwright.
- Fixtures are named for what they provide, not how (`authenticated_client`, not `client2`).

## Backend route test framework

Route tests inherit a shared suite instead of restating CRUD, auth and pagination per entity. The
implementation is in `tests/backend/routes/test_base/`, split by concern (`crud.py`,
`user_relationships.py`, `list_operations.py`, `authentication.py`, `edge_cases.py`,
`performance.py`, `health.py`). `base.py` is a re-export shim kept for existing imports.

`BaseEntityRouteTests` composes all of them into 30 tests: 11 CRUD, 7 user-relationship, 6 list
operations, 3 edge cases, and one each for authentication, performance and health.

```python
from .base import BaseEntityRouteTests, BaseEntityTests
from .endpoints import APIEndpoints


class CategoryTestMixin:
    entity_name = "category"      # user relationship fields are auto-detected from this
    entity_plural = "categories"
    endpoints = APIEndpoints.CATEGORIES

    def get_sample_data(self, client=None):
        return generate_category_data()

    def get_minimal_data(self, client=None):
        return TestDataGenerator.generate_category_minimal()

    def get_update_data(self):
        return TestDataGenerator.generate_category_update_data()


class TestCategoryStandardRoutes(CategoryTestMixin, BaseEntityRouteTests):
    pass


@pytest.mark.unit
class TestCategorySpecificEdgeCases(CategoryTestMixin, BaseEntityTests):
    """Only what's specific to categories — parent_id, entity_type filtering."""
```

Adding an entity takes two steps: a `BaseEntityEndpoints` subclass in `endpoints.py` registered on
`APIEndpoints`, and a mixin plus the two classes above. `get_sample_data` and `get_minimal_data`
receive the test client so an entity whose create payload needs a real foreign key can look one up.

Per-router coverage is tracked in [`backend/routes/STATUS.md`](./backend/routes/STATUS.md).

## Guides

- [Backend](./backend/README.md) — fixtures, database and API patterns
- [SDK](./sdk/README.md) — HTTP client mocking, integration setup
- [Penelope](./penelope/README.md) — mocking strategies for the agent
- [k6](./k6/README.md) — load test scenarios and thresholds

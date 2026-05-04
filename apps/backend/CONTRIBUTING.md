# Contributing

For the full contribution guide, see [docs.rhesis.ai/contribute/backend](https://docs.rhesis.ai/contribute/backend).

## Before you start
- Install [`uv`](https://docs.astral.sh/uv/) for Python environment management.

## Linting and formatting

From `apps/backend`:

```bash
make format      # auto-format and fix all Python files
make lint        # check formatting without modifying files
```

Both targets use [ruff](https://docs.astral.sh/ruff/) via `uvx`. There are also diff-scoped variants that only run against files changed relative to `main`:

```bash
make format_diff
make lint_diff
```

## Tests

From `apps/backend`:

- **Full suite** — `make test` starts the test Docker profile (PostgreSQL and Redis on host ports 12001 and 12002), then runs `pytest` on `../../tests/backend` (see the `Makefile` for flags).
- **Single test or file** — start the same stack, then run pytest yourself:

  ```bash
  make docker-up
  uv run --extra cpu pytest ../../tests/backend/models/test_foo.py::TestClass::test_name -v
  ```

  Your usual **dev** database containers (different ports) are not used; tests expect the `backend` profile in `tests/docker-compose.test.yml`.

- **Teardown** — `make docker-down` (or `make docker-clean` to remove volumes).

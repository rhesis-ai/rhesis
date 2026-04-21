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

## Tests and checks

From `apps/backend`, see `Makefile`: `make test` (uses the test Docker profile), `make format`, `make lint`, `make all`.

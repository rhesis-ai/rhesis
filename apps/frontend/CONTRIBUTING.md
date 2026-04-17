# Contributing

For the full contribution guide, see [docs.rhesis.ai/contribute/frontend](https://docs.rhesis.ai/contribute/frontend).

## Linting and formatting

From `apps/frontend`:

```bash
make format        # Prettier — write fixes (`npm run format`)
make format-check  # Prettier — check only (`npm run format:check`)
make eslint        # ESLint — fails if eslint output contains "Error:" (`npm run lint`)
```

Full gate (format check, types, ESLint, then `next build`): `make lint`. Without the production build step: `make lint-fast`. See targets in `Makefile`.

## Tests

From `apps/frontend`:

- **`make test`** — runs `npm test` with `--passWithNoTests --ci --watchAll=false` (see `Makefile`).
- **`./rh test frontend`** (repo root) — runs plain `npm test` in `apps/frontend` (see `test_frontend` in `rh`).
- **`make test-coverage`** — `npm run test:ci` (Jest with coverage reporters aligned with CI).

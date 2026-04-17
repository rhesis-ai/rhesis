# Contributing

For the full contribution guide, see [docs.rhesis.ai/contribute/frontend](https://docs.rhesis.ai/contribute/frontend).

## Linting and formatting

From `apps/frontend`:

```bash
make format        # Prettier — write fixes (`npm run format`)
make format-check  # Prettier — check only (`npm run format:check`)
make eslint        # ESLint — fails if eslint output contains "Error:" (`npm run lint`)
make type-check    # TypeScript — `tsc --noEmit` (`npm run type-check`)
```

Full gate (format check, types, ESLint, then `next build`): `make lint`. Without the production build step: `make lint-fast`. See targets in `Makefile`.

## Tests

From `apps/frontend`:

- **`make test`** — runs `npm test` with `--passWithNoTests --ci --watchAll=false` (see `Makefile`).
- **`./rh test frontend`** (repo root) — runs plain `npm test` in `apps/frontend` (see `test_frontend` in `rh`).
- **`make test-coverage`** — `npm run test:ci` (Jest with coverage reporters aligned with CI).

**E2E (Playwright):**

- **`make test-e2e`** — brings up `../../tests/docker-compose.frontend.yml`, sets env vars, then runs Playwright with `--grep "@sanity|@crud"` (see `Makefile`).
- **`make test-e2e-smoke`** — same Docker setup, `--grep "@sanity"` only.
- **`npm run test:e2e`** — `playwright test` only; no Docker or env wiring from the Makefile. Use when you already have a backend and env configured yourself.

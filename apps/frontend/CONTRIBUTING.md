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

## End-to-end (Playwright)

Changes under `apps/frontend/**` trigger **[Test] Frontend E2E** in CI. CI uses Docker for the Quick Start backend (`make test-e2e-ci`, Chromium only).

**Locally without Docker** (frontend + mocked API only):

```bash
cd apps/frontend
npx playwright install chromium   # once
make test-e2e-local               # @mocked tests on http://localhost:3100
```

This starts a dedicated dev server on port **3100** (so it does not clash with `npm run dev` on 3000), seeds auth without a backend (`E2E_NO_DOCKER=1`), and runs Playwright route mocks for API data.

**CI / full backend** (requires Docker):

```bash
make test-e2e        # @sanity|@crud on Chromium + Firefox (local)
make test-e2e-ci     # @sanity|@crud on Chromium only — same as CI
make test-e2e-smoke  # @sanity only
make docker-down     # tear down stack
```

Debug: `npm run test:e2e:ui` or `npm run test:e2e:headed`. Config: `playwright.config.ts`; specs: `tests/e2e/`.

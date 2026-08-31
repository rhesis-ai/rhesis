# Frontend tests

Frontend tests are the one exception to the repo's "tests live under `tests/`" rule — they sit with
the code they cover. This directory holds no tests; it exists to point at where they are.

## Where they live

| Kind | Location | Runner |
| --- | --- | --- |
| Unit / component | `apps/frontend/src/**/__tests__/`, `apps/frontend/src/**/*.test.tsx` | Jest |
| EE unit / component | `ee/frontend/src/**/__tests__/` | Jest |
| E2E | `apps/frontend/tests/e2e/tests/*.spec.ts` | Playwright |

Jest discovery is configured in `apps/frontend/jest.config.js`, which adds `ee/frontend/src` to
`roots` so EE tests run in the same pass as core ones. Playwright's `testDir` is
`apps/frontend/tests/e2e`.

## Running

```bash
cd apps/frontend
npm test                          # all Jest tests
npm test -- --watch
npm test EntityGrid               # by filename pattern
npm run test:ci                   # coverage, as CI runs it

make test-e2e                     # @sanity + @crud against a Docker backend on 14003
make test-e2e-smoke               # @sanity only
make test-e2e-local               # @mocked, no Docker
make docker-down
```

`make test-e2e-local` needs no backend: Playwright starts `tests/e2e/mock-backend.mjs` on
127.0.0.1:8080, seeds auth from a fixture JWT instead of logging in, and serves the app on port
3100 so it doesn't clash with a dev server on 3000.

## Jest setup

`jest.polyfills.js` runs before the environment (it supplies `structuredClone`, which jsdom lacks
and `@mui/x-internal-gestures` needs). `jest.setup.js` then extends matchers with `jest-dom` and
`jest-axe`, and stubs what jsdom doesn't implement: `next/router` and `next/navigation`,
`matchMedia`, `ResizeObserver`, `IntersectionObserver`, `localStorage`/`sessionStorage`,
`window.location`.

`@testing-library/react` is remapped to `src/test-utils.tsx`, so a plain `render()` already comes
wrapped in the MUI `ThemeProvider` and a fresh `QueryClient` per test. Import it as
`@testing-library/react` and don't add your own providers unless the test needs different ones.
(`jest.config.js` declares that mapping twice; the later `src/test-utils.tsx` entry is the one that
takes effect, so `src/test/testing-library-react.tsx` is unreachable.)

A file needing the node environment (middleware tests using `NextRequest`) opts in with a
`@jest-environment node` docblock; the `window` stubs above then don't apply.

## Mocking

- API calls: MSW v2 (`http`/`HttpResponse`, not the v1 `rest` API). Default handlers live in
  `src/__mocks__/msw/handlers.ts`, the node server in `src/__mocks__/msw/server.ts`. Extend
  handlers per test with `server.use(...)`.
- Entity fixtures: factories in `src/__mocks__/test-utils.tsx` — `createMockProject`,
  `createMockTestRun`, `createMockTestSet`, `createMockEndpoint`, `createMockPaginatedResponse`,
  and others. All take an overrides object.

## E2E structure

```
apps/frontend/tests/e2e/
├── auth.setup.ts     # runs first, writes storageState to .auth/user.json
├── tests/            # *.spec.ts
├── pages/            # page objects, one per screen
├── helpers/          # MockApiHelper, CrudHelper, RbacMockHelper, PerformanceHelper
├── fixtures/         # JSON API responses
└── mock-backend.mjs  # stands in for the backend under E2E_NO_DOCKER=1
```

Specs carry tags, and both the Playwright projects and the Make targets select on them:

| Tag | Runs under | Covers |
| --- | --- | --- |
| `@sanity` | `make test-e2e`, `test-e2e-smoke`, CI | cross-browser smoke set (Chromium + Firefox) |
| `@crud` | `make test-e2e`, CI | create/edit/delete flows, Chromium |
| `@mocked` | `make test-e2e-local` | deterministic empty/populated/error states |
| `@visual` | manual only | screenshot baselines |
| `@performance` | manual only | LCP/TTFB/Load thresholds |

`@visual` and `@performance` have Playwright projects but no Make target and no scheduled
workflow — nothing runs them unless you invoke them yourself
(`npx playwright test --project=visual`). The comments in `playwright.config.ts` calling them
nightly describe an intent, not a job that exists.

Tag every new spec. CI runs `make test-e2e-ci-no-build`, which greps for `@sanity|@crud`, so an
untagged spec silently never runs there. CI also shards Chromium three ways via
`PLAYWRIGHT_SHARD` — specs must not depend on each other or on ordering.

## See also

- [`apps/frontend/src/__tests__/README.md`](../../apps/frontend/src/__tests__/README.md) — writing
  component, hook and integration tests
- [`apps/frontend/AGENTS.md`](../../apps/frontend/AGENTS.md) — affordances, BFF auth, TypeScript
  conventions

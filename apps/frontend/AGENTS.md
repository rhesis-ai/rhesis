# Frontend Rules

Next.js 16 with App Router and Material UI. See root `AGENTS.md` for repo-wide rules.

Authenticated routes live under `src/app/(protected)/`; backend calls go through the typed clients
in `src/utils/api-client/`.

## Affordances (Server-Driven Permissions)

The backend resolves permitted actions per object (see `apps/backend/AGENTS.md`). The frontend
consumes them through **three primitives only** — never roll your own ownership logic
(`user.id === currentUserId`).

| Primitive                           | When to use                                                                                                       |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `can(subject, Capability.X.Y)`      | Object already in scope and its type extends `WithPermittedActions`. Checks the object's own `permitted_actions`. |
| `useCan(Capability.X.Y)`            | No object in scope (page guard, create button, editable prop). Checks the caller's ambient scope set.             |
| `<Can capability={Capability.X.Y}>` | Same as `useCan` but declarative JSX — wraps buttons/FABs.                                                        |

```tsx
// Object-level — subject carries permitted_actions
const canUpdate = can(experiment, Capability.Experiment.UPDATE);

// Ambient — scope/role check, no object
const canRead = useCan(Capability.TestRun.READ);
if (!canRead) return <AccessDenied resource="test runs" />;

// Declarative
<Can capability={Capability.TestSet.CREATE}>
  <Fab icon={<FabAddIcon />} />
</Can>;
```

A type carries object-level affordances if it extends `WithPermittedActions` — check with
`grep -rn "extends WithPermittedActions" src`. Everything else uses `useCan`/`<Can>`.

Every protected page must guard its READ capability with the `useCan` pattern above.

Adding affordances to a new resource: extend the TS interface with `WithPermittedActions` from
`@/types/affordances`, use `can(subject, …)` instead of `useCan`, and add the new capability string
to `src/constants/capabilities.ts` (must mirror the backend `Permission` enum).

**Import all four primitives from `@/components/common/Can`**, including `can` — that module
re-exports it from `@/utils/affordances`. Both paths work at runtime, but only one is mockable in
one place: a test that mocks `@/components/common/Can` does not intercept a component importing
`can` from `@/utils/affordances`, and the check silently runs for real. Import `@/utils/affordances`
directly only from non-React code (e.g. `src/utils/server-permissions.ts`).

Tests rendering a component that uses any affordance primitive must mock the module:

```ts
jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));
```

## BFF Auth Pattern (no client-side session tokens)

Authenticated calls from client components go through the same-origin `/api/backend/...` proxy,
which injects `Authorization` server-side from the httpOnly session cookie. The access token must
never reach a browser-issued fetch — don't prop-drill a `sessionToken` string into client
components, hooks, or utils.

- **Instantiate `new ApiClientFactory()` with no arguments** in client components/hooks/utils.
  `buildAuthHeaders()` in `src/utils/api-client/base-client.ts` only attaches `Authorization` when
  `typeof window === 'undefined'` — a token passed from client code is silently dropped, so adding
  one back doesn't "fix" anything, it just leaves dead prop-drilling for the next person to trip
  over.
- **Only server-side code** (Server Components, Route Handlers, Server Actions —
  `src/utils/api-client/server-factory.ts`) passes an explicit token/`projectId` into
  `ApiClientFactory`.
- **Gate on auth state with `isAuthenticated(status)` / `useIsAuthenticated()`** from
  `src/hooks/useIsAuthenticated.ts` (checks NextAuth's `useSession().status`), not on
  `session?.session_token` presence. The old token-presence check silently breaks once a component
  stops receiving a token.
- **Tests**: any `jest.mock('next-auth/react', ...)` mock of `useSession` must include
  `status: 'authenticated'` alongside `data` — components gating on `isAuthenticated(status)` hang
  in a loading state forever if the mock omits `status`.

This isn't optional style — a PR that reintroduces `sessionToken` prop-drilling on a new feature
merged cleanly with BFF-migrated code and broke lint, unit tests, and every E2E shard (the merge
was textually clean but semantically broken: the dangling `sessionToken` reference didn't exist as
a conflict, just a runtime `ReferenceError`). When adding a feature that needs the backend from a
client component, follow the pattern above rather than copying an older prop-drilled example.

## Feature Gating — frontend side

`src/constants/features.ts` (`FeatureName`) and `src/constants/capabilities.ts` (`Capability`) are
hand-mirrored from the backend enums and must stay in sync with them.

`FeaturesProvider` (mounted in the protected layout) + `useFeature(name)` +
`<FeatureGate feature={...}>` consume `GET /features` to conditionally render gated UI.
Fail-closed: features are `false` during the initial fetch and on error. See
`apps/backend/AGENTS.md` for the registration flow behind them.

## TypeScript & ESLint Conventions

The following are enforced as warnings/errors and must pass with **zero** issues before
committing — run all three:

```bash
npm run format        # Prettier
npx tsc --noEmit       # type checking
npm run lint           # ESLint
```

- **No `any`** (`@typescript-eslint/no-explicit-any`). Use `unknown` and narrow with `instanceof`/
  `typeof`/`Array.isArray()`, or the correct library type (e.g. MUI's `GridRowParams`, `SxProps<Theme>`,
  Recharts formatter types). Last resort: `as unknown as TargetType`. Exception: test files may use
  `any` for mocks — add `/* eslint-disable @typescript-eslint/no-explicit-any */` at the top.
- **`unknown` leaking into JSX**: values typed `Record<string, unknown>` (e.g. `metadata`) must be
  extracted and narrowed to a concrete type/boolean _before_ use in JSX conditionals or children —
  raw `unknown` in a `&&` chain fails `TS2769`. Guard API values that may be `{}` with `typeof`
  checks before passing to `new Date()`, string methods, etc.
- **No non-null assertions** (`!`) — use optional chaining or explicit `if` checks instead.
- **`react-hooks/exhaustive-deps`** — list all reactive values used in `useEffect`/`useCallback`/
  `useMemo`. If adding a dependency would cause an infinite loop, disable inline with a reason:
  `// eslint-disable-next-line react-hooks/exhaustive-deps -- only run on mount`.
- **Unused vars/params/destructured values** (`@typescript-eslint/no-unused-vars`): prefix with `_`
  (e.g. `_event`, `_index`, `{ key: _key, ...rest }`), or remove entirely if truly not needed.
- **No array index as React key** (`react/no-array-index-key`) — use a stable id. For display-only
  lists that never reorder, `eslint-disable-next-line` with a justification is acceptable.
- **Console**: only `console.warn`/`console.error` — no `console.log`.
- Combine imports from the same module; use `import type` for type-only imports.

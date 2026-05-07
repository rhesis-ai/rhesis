# rhesis-frontend-ee

Enterprise Edition frontend code for Rhesis. Licensed under the
[Rhesis Enterprise License](../LICENSE).

This directory hosts UI for enterprise features (SSO today, more to come).
It is wired into the Next.js app at `apps/frontend/` via a single path
alias (`@ee/*`) and a single sanctioned bridge file
(`apps/frontend/src/ee_bootstrap.ts`). Together those are the entire
core-to-EE coupling on the frontend; the inverse direction is
unrestricted (EE may import freely from `@/`).

## Structure

```
ee/frontend/src/
  index.ts                       re-export of bootstrap entry point
  bootstrap.ts                   registers EE features into core registries
  sso/                           Single Sign-On
    components/
      SSOConfigForm.tsx          rendered as an org-settings section
    api/
      sso-client.ts              4 SSO methods (extends BaseApiClient)
    types.ts                     SSOConfig, SSOTestResult shapes
```

## Boundary rule

Core (`apps/frontend/`) must **never** statically import from `@ee/*`.
The only allowed exception is `apps/frontend/src/ee_bootstrap.ts`,
which exists for exactly this purpose. EE code is free to import from
`@/` (core).

Two layers of enforcement:

1. **ESLint `no-restricted-imports`** (`eslint.config.mjs`) -- catches
   violations during local development and in IDE.
2. **CI boundary script** -- `apps/frontend/scripts/check-ee-boundary.mjs`
   walks `apps/frontend/src/` with regex on `import`/`require`
   statements and exits non-zero on any unauthorised `@ee/*` reference.
   Wired as the `community-boundary` job in `frontend-test.yml`. Pure
   Node, no `npm install`, runs in seconds. Mirror of the backend's
   `community-boundary` job.

## Tests

Frontend convention is colocated tests, so EE tests live next to their
source under `ee/frontend/src/<feature>/__tests__/`. Jest's `roots`,
`testMatch`, `moduleNameMapper`, `modulePaths`, and
`collectCoverageFrom` in `apps/frontend/jest.config.js` are all
extended to cover `ee/frontend/src/`, so:

- `npm run test` and `npm run test:ci` (run from `apps/frontend/`)
  pick up EE tests automatically.
- Coverage reports include EE feature code.
- EE tests can import via `@/...` (core) or relative paths (intra-EE).

Reference test files:

- `ee/frontend/src/__tests__/bootstrap.test.ts` -- smoke test that
  `bootstrapEE()` registers SSO into the `organization-settings`
  registry idempotently.
- `ee/frontend/src/sso/api/__tests__/sso-client.test.ts` -- pins the
  SSO API URL/method contract.

The same architectural shape applies on the backend: see
`ee/backend/README.md` for the symmetric Python rule, its AST-based
guard, and the backend test layout under `tests/backend/ee/`.

## Adding a new EE feature

The procedure is mechanical -- pick the shape that matches your feature,
follow the recipe, and the boundary stays clean.

### Shape A: section inside an existing core page

Example: a SAML or SCIM section on the organization-settings page,
alongside SSO.

1. Build the component under `ee/frontend/src/<feature>/components/`.
2. Add `FeatureName.<NEW_FEATURE>` to
   `apps/frontend/src/constants/features.ts`.
3. Register it in `bootstrap.ts`:
   ```ts
   import { registerOrgSettingsSection } from '@/lib/extension-registries';
   registerOrgSettingsSection({
     id: '<feature>',
     title: '<Display Title>',
     feature: FeatureName.<NEW_FEATURE>,
     component: <YourComponent>,
     order: 200,
   });
   ```

That's it. The settings page iterates the registry, wraps each entry in
a `<FeatureGate>`, and your section renders when the feature is
licensed and the org has it enabled.

### Shape B: new top-level page

Example: an audit log at `/audit-log`.

1. Build the page component at
   `ee/frontend/src/<feature>/page.tsx`. It can be a Server or Client
   Component, same rules as core pages.
2. Create a thin re-export at
   `apps/frontend/src/app/(protected)/<feature>/page.tsx`:
   ```ts
   import EEPage from '@ee/<feature>/page';
   export default EEPage;
   ```
   This is the only file in core that may name the EE module. The
   ESLint guard exempts it via the same allow-list as
   `ee_bootstrap.ts` (extend the rule's `files` override when adding
   the first such page).
3. Register the nav entry in `bootstrap.ts`:
   ```ts
   import { registerAdminNavItem } from '@/lib/extension-registries';
   registerAdminNavItem({
     id: '<feature>',
     title: '<Title>',
     path: '/<feature>',
     feature: FeatureName.<NEW_FEATURE>,
     order: 50,
   });
   ```

### Shape C: a UI surface that no existing registry covers

Example: a widget on the dashboard, a custom column on the Tests data
grid, an extra tab on test-result detail.

This is the only shape that requires touching core. The cost is once per
new shape, then every subsequent feature of that shape is shape A:

1. Pick a name for the seam (e.g. `dashboard-widgets`).
2. Add `apps/frontend/src/lib/extension-registries/<seam>.ts` following
   the existing template (`organization-settings.ts` is the
   reference). Implement `register*Item`, `get*Items` (sorted by
   `order`), and `reset*Items` (test-only).
3. Re-export the public API from
   `apps/frontend/src/lib/extension-registries/index.ts`.
4. Modify the core component that renders the corresponding UI surface
   (e.g. `apps/frontend/src/app/(protected)/dashboard/page.tsx`) to
   call `get*Items()` and render each.
5. Document the seam under "Extension points" in this README.

The rest is shape A.

## Extension points published by core

Each entry below is a registry in
`apps/frontend/src/lib/extension-registries/`. EE plugs into them from
`bootstrap.ts`. Adding a new entry below is the natural place to
document a freshly added seam.

### `organization-settings`

Inserts a section into the organization-settings page below the
built-in Basic Information / Contact Information sections and above the
Danger Zone. Used today by SSO. Each entry can declare a
`FeatureName`, in which case core wraps the section in a
`<FeatureGate>` automatically.

### `admin-nav` (preemptive, no consumer yet)

Allows EE to register top-level admin navigation items for features
that ship a dedicated page. Not consumed by `app/layout.tsx` today --
the consumer will be added at the same time as the first feature that
needs it (likely the audit log). Listed here so the registration call
is the same shape as future entries.

## License providers

License-driven gating happens server-side via the backend's
`/features` endpoint. The frontend reads this endpoint once on mount
in `FeaturesProvider` and exposes the result via `<FeatureGate>` and
`useFeature()`. EE components do not need to do anything beyond
declaring `feature: FeatureName.<X>` in their registration -- core
takes care of wrapping the render.

## Removing EE for an MIT-only build

To produce a build that contains zero enterprise code:

1. Delete `ee/frontend/`.
2. Replace the body of `apps/frontend/src/ee_bootstrap.ts` with
   `export {};` (a no-op).
3. Optionally remove the `@ee/*` entry from
   `apps/frontend/tsconfig.json` and the alias in
   `apps/frontend/next.config.mjs`.

The boundary guard guarantees these are the only files that need
editing -- nothing else in `apps/frontend/` references `@ee/*`.

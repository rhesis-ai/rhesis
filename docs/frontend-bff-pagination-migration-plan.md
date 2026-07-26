# Frontend BFF + Server-Pagination Migration Plan

**Status:** Draft
**Owner:** Frontend
**Origin:** [PR #2267](https://github.com/rhesis-ai/rhesis/pull/2267) — metrics/behaviors server-driven pagination

## 1. Background

The metrics and behaviors directory pages used to:

- Fetch **all** matching rows client-side (`getAllMetrics()` / `getBehaviors()` looping
  through 100-item pages) and paginate/filter/sort in memory.
- Show a client-side loading spinner on every first load, even though the data was
  static and cheap to fetch server-side.
- On create/edit/delete, either mutate local state ad hoc or (in an interim version)
  blindly re-fetch the current page — which could hide a just-created row if it
  sorted outside page 0 (caught by the `behaviors-crud.spec.ts` E2E suite).

PR #2267 replaced this with two reusable primitives:

- **[`prefetchList`](../apps/frontend/src/utils/server-prefetch.ts)** — a server-side
  helper used from a page's `page.tsx` (a Next.js Server Component). It checks the
  capability required to read the entity (`hasServerCapability`), and if allowed,
  fetches the first page through the BFF proxy (`createServerApiFactory()`) and
  returns `{ initialData, initialTotalCount }` to seed the client component. This
  eliminates the first-load spinner and avoids serializing data the user isn't
  authorized to see.
- **[`usePaginatedList`](../apps/frontend/src/hooks/usePaginatedList.ts)** — a client
  hook that owns `page`/`rowsPerPage` state, resets to page 0 on filter change,
  clamps the page when the result set shrinks, and re-fetches via a
  `fetchPage({ skip, limit })` callback the caller supplies (closing over OData
  filters). It's idempotent under React 18 Strict Mode's double-invoked mount
  effects via a request-signature ref, rather than a one-shot flag.

This plan scopes rolling the same pattern out to the rest of the app's directory/list
pages.

## 2. Backend foundations this plan builds on

The frontend pattern in §1 only works because of backend work landed alongside it.
Any page migrated per §5 needs to confirm these are already in place for its
entity, or budget backend work first:

- **Explicit eager-loading via `QueryBuilder`**
  (`apps/backend/src/rhesis/backend/app/utils/query_utils.py`). List endpoints
  (`crud.get_metrics`, `crud.get_behaviors`, etc.) build queries with
  `joinedload`/`selectinload` chains scoped to exactly what the frontend needs,
  rather than relying on lazy-loaded relationships (which caused N+1 queries) or
  a generic `with_default_derived_field_loads()` that silently skipped
  many-to-many relationships (e.g. `Metric.behaviors`).
- **Two-phase ("id-then-join") pagination**: list endpoints fetch matching row IDs
  with a simple, unjoined query first, then eager-load relationships only for the
  page's IDs in a second query. This avoids building expensive joins for rows that
  get thrown away by pagination, and avoids cartesian-product blowup from
  many-to-many joins on the full result set.
- **`X-Total-Count` header + `PaginatedResponse` contract**: every migrated list
  endpoint returns a total count (via header, on `metric.py`/`behavior.py`) so the
  frontend can render `TablePagination` without a separate count query. Any entity
  whose endpoint doesn't set this header yet (see §5.3's "needs adapter" column)
  needs it added before `usePaginatedList` can drive its pagination UI directly.
- **OData `$filter` support, including `any()` navigation filters**: the
  `odata_query` library compiles filters like
  `behaviors/any(b: tolower(b/name) eq tolower('Toxicity'))` into an `EXISTS`
  subquery through the association table, letting the frontend filter on a
  many-to-many relationship without fetching everything client-side. This is
  covered by a regression test
  (`TestODataAnyNavigationFilter` in `tests/backend/utils/test_query_builder_load.py`)
  added specifically because it isn't obvious this is supported. Pages in §5.2
  need endpoint-side OData filtering added if they don't have it (Tokens, Explorer).
- **Custom non-OData filters where OData can't express the need**: `metric_scope`
  is a Postgres JSONB array column, filtered via a `@>` (contains) operator
  through a dedicated `metric_scope` query parameter and
  `crud._apply_metric_scope_filter()` helper, rather than forcing it through OData
  syntax. `$select` is a similar case — a comma-separated field list to shrink the
  response payload (used by metrics to drop fields the directory grid doesn't
  render). New pages may need similar narrow, purpose-built parameters rather than
  trying to force every filtering need through generic OData.
- **Tenant isolation is automatic for ORM queries**: the `before_compile` listener
  applies `WHERE organization_id = ...` to every ORM query, including the ones
  built by `QueryBuilder`. This only holds for ORM/Core queries — any future
  backend work using raw SQL for a list endpoint (e.g. a `json_agg`/`LATERAL`
  single-query approach considered and rejected for metrics/behaviors in favor of
  the two-phase approach) would need to apply this filter manually.

None of the pages in §5.1/§5.2 are currently blocked on backend work beyond what's
listed per-entity (Tokens' `$filter`, Explorer's total count). Everything in §5.3
already has working backend pagination/filtering; their gap is purely on the
frontend (SSR prefetch).

## 3. Goals

1. Eliminate client-side "fetch everything, paginate/filter in memory" patterns
   (`getAllX()` loops, hardcoded `limit: 50/100` caps with in-memory `.filter()`).
2. Eliminate avoidable first-load spinners on directory pages via SSR prefetch,
   gated by the same server-side capability check used for the client gate.
3. Standardize OData filter construction (`buildXODataFilter` helpers) instead of
   naive JS array filtering, where not already present.
4. Ensure CRUD operations don't rely on "refetch current page and hope the mutated
   row is still visible" — follow the behaviors fix (local sorted insert/update/
   remove, or a create-safe re-fetch strategy) instead.

## 4. Non-goals

- Migrating pages that already do server-side pagination via `useGridQuery` +
  React Query away from React Query. React Query's cache/invalidation model is a
  legitimate alternative to `usePaginatedList`; those pages mostly need SSR
  prefetch, not a hook swap. Forcing a hook migration would be higher risk for
  marginal benefit.
- Rewriting non-list pages (detail pages, dashboards, wizards).
- Changing backend query/filter capabilities beyond what's needed to unblock a
  given page (e.g. adding `$filter` support to an endpoint that lacks it).

## 5. Survey of candidate pages

Audit performed via [Survey](fac00d4a-907f-4db2-abec-2a50bb2aee8d) against
`apps/frontend/src/app/(protected)/`. `createServerApiFactory()` already exposes
every list entity's client, so no server-factory gaps block SSR prefetch anywhere
below.

### 5.1 Already migrated

| Entity | Notes |
|---|---|
| Metrics | Reference implementation — `page.tsx` + `prefetchList`, `MetricsClient.tsx` + `usePaginatedList`, `buildMetricODataFilter`. |
| Behaviors | Same pattern; CRUD uses local sorted insert/update/remove (`insertBehaviorSorted`) instead of blind refetch — this is the template for CRUD-safe mutations. |

### 5.2 True pagination gaps (client fetches everything or a hardcoded cap, filters in memory)

These are the highest-value targets — real data-over-fetching and no filter/pagination
push-down to the backend.

| Entity | Route | Current fetch | API method available | OData helper | Effort |
|---|---|---|---|---|---|
| Projects | `/projects` | `getAllProjects()` + client `.filter()`/`.slice()` | `getProjects` (paginated) exists, unused | Missing — needs `buildProjectODataFilter` | Medium |
| Models | `/models` | `getModels()` capped at 50, client filter | `getModels` supports `$filter`/pagination | Missing | Medium–large |
| Tools | `/tools` | `getTools({ limit: 100 })`, client filter | Already paginated/`$filter`-capable | Missing | Small–medium |
| Tokens (API keys) | `/tokens` | `listTokens({ limit: 100 })`, client filter + pagination | Paginated, but **no `$filter`** yet | Missing / needs backend | Medium |
| Explorer | `/explorer` | `getExplorerTestSets()` returns a bare array (no total count), client search + pagination | Needs API shape change to `PaginatedResponse` | Missing | Large |

**Risks:** Projects has sort-sensitive create (name-sorted) — apply the behaviors
CRUD fix directly. Models' 50-item cap can silently hide models and affects
default-model validation, which depends on seeing the full connected set. Explorer's
API doesn't return a total count at all, so it needs a small backend/API contract
change before `prefetchList`/`usePaginatedList` can be used as-is.

### 5.3 Already server-paginated — SSR prefetch is the main gap

These already push pagination/filtering to the backend (via `useGridQuery` + React
Query, or a manual paginated fetch), so the primary win is adding `prefetchList` to
their `page.tsx` to remove the first-load spinner. They can keep React Query for
subsequent client-side fetching/caching/invalidation — no hook migration needed.

| Entity | Route | Current client fetch | Response shape | OData helper |
|---|---|---|---|---|
| Endpoints | `/endpoints` | `useGridQuery` + `getEndpoints` | `PaginatedResponse` | `buildEndpointListFilter` |
| Tests | `/tests` | Page-scoped + OData | `PaginatedResponse` | `combineTestFiltersToOData` |
| Test sets | `/test-sets` | Page-scoped + OData | `PaginatedResponse` | `combineTestSetFiltersToOData` |
| Knowledge (sources) | `/knowledge` | Page-scoped + OData | `PaginatedResponse` | `combineSourceFiltersToOData` |
| Test runs | `/test-runs` | Page-scoped + OData | `PaginatedResponse` | `combineTestRunFiltersToOData` |
| Tasks | `/tasks` | `useGridQuery` + OData | `{ data, totalCount }` — needs adapter | `combineTaskFiltersToOData` |
| Experiments | `/experiments` | Manual paginated fetch + OData | `PaginatedResponse` | `combineExperimentFiltersToOData` |
| Annotations | `/annotations` | Page-scoped, dedicated query params (not OData) | `{ data, totalCount }` — needs adapter | N/A (query params) |
| Team members (org settings) | `/organizations/settings?tab=team` | `getUsers({ skip, limit, $filter })` | `{ data, total }` — needs adapter | `combineTeamFiltersToOData` |

**Risks:** Test runs shows near-real-time status (in-progress runs) — depends more
on React Query's refetch/polling than a one-time SSR prefetch buys much; low
priority for this reason. Test sets has async background imports (Garak) that can
make the list lag behind; SSR prefetch doesn't change that but shouldn't make it
worse. Any endpoint returning `{ data, totalCount }` or `{ data, total }` instead of
the standard `PaginatedResponse` shape needs a thin adapter before `prefetchList`
can consume it directly.

### 5.4 Special cases (defer)

| Entity | Route | Why deferred |
|---|---|---|
| Traces | `/traces` | Custom telemetry query model (`buildTraceQueryParams`), not standard OData; project-scoped fail-closed permissions. SSR prefetch alone is feasible; full pattern unification is medium–large and lower priority. |

## 6. Guardrails learned from the behaviors CRUD bug

When migrating a page's create/update/delete flows away from "fetch everything, splice
locally":

1. **Never replace an optimistic local mutation with a blind "refetch current page"**
   unless the list's sort order guarantees the mutated row stays on the current page
   (e.g. sorted by `created_at desc`, so new rows always land on page 0).
2. If the page is sorted by a field where a new/edited row could land anywhere
   (e.g. `name asc`), mutate local state directly instead:
   - **Create:** fetch the full detail object for the new row and insert it into
     local state in sorted position (`insertBehaviorSorted`-style helper), and bump
     `totalCount` by hand via the `setTotalCount` escape hatch `usePaginatedList`
     exposes.
   - **Update:** patch the matching row in place and re-sort if the sorted field
     changed.
   - **Delete:** filter the row out locally and decrement `totalCount`.
3. Add or extend an E2E test for each migrated page's create flow that asserts the
   created row becomes visible without a manual page reload — this is what caught
   the original regression.

## 7. Suggested execution order

1. **Quick SSR-prefetch wins** (already paginated, just need `prefetchList` added to
   `page.tsx`): Knowledge, Endpoints, Annotations, Experiments, Tasks.
2. **True pagination fixes** (real over-fetching / no filter push-down): Projects →
   Models → Tools → Tokens.
3. **Heavier grids** (complex multi-filter UI, bulk actions): Tests, Test sets,
   Test runs.
4. **Special cases last**: Traces, Explorer (needs API shape change first), Team tab.

Each item should land as its own small PR (per repo convention), following the
metrics/behaviors PR as the reference implementation, and should include:
- The `prefetchList` addition to `page.tsx` (and a capability-gated fallback to
  client fetching, matching the existing pattern).
- A `buildXODataFilter` helper if the page currently filters in memory.
- CRUD state updates audited against the guardrails in §6.
- An E2E assertion that a newly created row becomes visible without a reload.

## 8. Open questions

- For pages already on `useGridQuery`/React Query (§5.3), do we want `prefetchList`
  to hydrate React Query's cache directly (via `initialData` on the query), or just
  pass `initialData` as a prop the client component renders before the first query
  resolves? The former avoids a flash-then-refetch; the latter is simpler and matches
  what metrics/behaviors already do.
- Should `usePaginatedList` gain first-class support for entities whose API returns
  `{ data, totalCount }` / `{ data, total }` instead of the standard
  `PaginatedResponse`, or should each such client be updated to return
  `PaginatedResponse` for consistency? The latter is more invasive per-client but
  keeps `prefetchList`/`usePaginatedList` free of shape-adapter logic.
- Tokens needs backend `$filter` support before its filters can be pushed
  server-side — worth scoping as a small backend PR ahead of the frontend migration.
- Explorer's `getExplorerTestSets()` needs a total-count-bearing response shape
  before it can adopt `prefetchList`/`usePaginatedList` at all — same backend
  dependency as above.

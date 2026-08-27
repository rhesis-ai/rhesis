# Backend Rules

FastAPI REST API with Celery task processing. Layered: routers → services → models/crud.
See root `AGENTS.md` for repo-wide rules (commits, PRs, testing overview, tech stack).

## Directory layout

- `src/rhesis/backend/app/` — FastAPI core: `models/` (SQLAlchemy ORM), `schemas/` (Pydantic),
  `routers/`, `services/` (business logic), `auth/`, `scope.py`/`models/scope_events.py` (tenant
  scope), `features/` (feature gating)
- `alembic/` — DB migrations
- `jobs/` — Celery background tasks (`execution/`, `telemetry/`)
- `metrics/` — evaluation metrics (DeepEval, RAGAS, native providers)

## Imports

**Always absolute, never relative.** Write the full dotted path, including for a module's own
siblings:

```python
from rhesis.backend.app.schemas.explorer import TestTreeNode  # yes
from rhesis.backend.app.services.explorer.utils import build_test_tree  # yes
from .utils import build_test_tree  # no
from ..database import get_db  # no
```

This holds inside a package's own `__init__.py` too. Existing relative imports are being converted
as the files around them are touched.

## CRUD layout

`app/crud/` is one module per entity — `crud/test.py`, `crud/test_set.py`, `crud/explorer.py`, and so on.
`crud/__init__.py` is empty on purpose; **a new CRUD function goes in its entity's module**, and a
new entity gets a new module.

Layering is routers → services → crud, and the same "split, don't grow" rule runs down it: touching
a router means its business logic moves into a service; touching a service means its SQL moves into
`crud/`. No SQL in routers.

Import the function directly — `from rhesis.backend.app.crud.explorer import
set_explorer_test_outputs`. Reaching through the parent (`from rhesis.backend.app import crud`, then
`crud.explorer.foo()`) raises `AttributeError` unless some other module happens to have imported the
submodule already, which makes it work by accident.

## Jobs layout

`jobs/` is Celery orchestration only — no business logic. Anything reusable outside a Celery
context (model resolution, response parsing, error detection) belongs in `app/services/` or
`app/utils/`; `jobs/` depends on those, never the reverse. Importing anything under
`rhesis.backend.jobs` builds the whole Celery app first (`jobs/__init__.py` eagerly imports every
task module), so a `services/` import from `jobs/` silently drags all of that in.

A "task" in this codebase is a human to-do (the `task` table, the Tasks screen). Background work is
a "job". Celery's own vocabulary — `@app.task`, `AsyncResult`, `self.request.id` — is framework API
and stays as-is; it is confined to `jobs/`.

Use `app/utils/` over `app/services/<domain>/` when more than one unrelated service needs the
helper — e.g. `app/utils/response_extractor.py` is used by explorer's invocation *and* by metric
evaluation, batch execution, and Penelope, none of which are endpoint-specific.

## Testing and debugging

Running the test suite and debugging the backend directly each have their own skill —
invoke `backend-testing` or `backend-debug` when doing that task.

## Ambient Request Scope (Tenant Filtering & Stamping)

All tenant context (`organization_id`, `user_id`, `project_id`) is stored **once per request** on
`Session.info['_scope']` by `get_db_with_tenant_variables()` and automatically applied by two
SQLAlchemy event listeners — no explicit threading through router, service, or CRUD parameters is
needed.

> **Note:** The `ContextVar` (`_scope`) is **not** used for normal FastAPI/Celery request paths.
> It is only for scripts and tests that call `bind_scope()` explicitly. Do **not** call
> `current_scope()` from inside a request handler and expect it to reflect the active project —
> use `db.info.get('_scope')` instead.
>
> This is about `_scope` specifically, and the reason is that it is bound by a **sync**
> dependency, which FastAPI runs in the anyio threadpool where a `ContextVar` write cannot escape
> back to the handler's task. An `async def` dependency does not have that problem —
> `app/usage_attribution.py` relies on it. See "Usage attribution" below.

### How it works

`scope.py` defines:

- `RequestScope` — frozen dataclass holding the identity triple
- `_scope: ContextVar[RequestScope]` — for scripts/tests via `bind_scope()` only; **not** set on
  the normal request path
- `_tenant_filter_disabled: ContextVar[bool]` — separate bypass flag

`models/scope_events.py` registers two listeners:

- `auto_filter` (`Session.do_orm_execute`) — adds `WHERE organization_id=...` (and `project_id=...`)
  to every SELECT, UPDATE, DELETE automatically, including `db.execute(select(...))` and
  relationship lazy/eager loads
- `auto_stamp` (`Session.before_flush`) — fills `organization_id`, `user_id`, `project_id` on new
  ORM objects when the column is `None`

### Using the scope

```python
# Normal FastAPI route — nothing extra to do. Scope is bound by get_db_with_tenant_variables.

# Admin / cross-org read:
from rhesis.backend.app.scope import bypass_tenant_filter

with bypass_tenant_filter():
    all_rows = db.query(SomeModel).all()  # filter skipped; stamp still active

# Background scripts / migrations (scope is unbound outside get_db_with_tenant_variables):
from rhesis.backend.app.scope import RequestScope, bind_scope, reset_scope

token = bind_scope(RequestScope(organization_id="...", user_id="..."))
try:
    ...
finally:
    reset_scope(token)
```

### Limitations

- `Session.bulk_insert_mappings` / `bulk_save_objects` bypass `before_flush` AND `do_orm_execute`;
  neither auto-stamp nor auto-filter apply. Include `organization_id`/`user_id`/`project_id` in
  bulk payloads manually.
- Raw SQL `INSERT`/`UPDATE`/`DELETE` bypasses both listeners. Auth uses some intentionally; tenant-
  scoped raw SQL must add explicit `WHERE` clauses or rely on RLS.
- Background scripts run outside `get_db_with_tenant_variables`. Bind scope explicitly or pass
  identity in model constructors.

### Kill switch

Set `RHESIS_DISABLE_SCOPE_LISTENER=1` to disable both listeners without redeploying.

### Test fixtures

`tests/backend/conftest.py` provides:

- `isolate_request_scope` (autouse) — resets `ContextVar`s to defaults per test; existing tests
  are unaffected because the listener no-ops when `organization_id is None`
- `bound_scope` — opt-in fixture for tests that exercise the listeners directly

### Side-channel and in-request scope binding

Three functions set tenant GUCs and/or the ORM auto-filter scope. Use the table below —
do not default to `bind_scope_to_session`.

| Situation                                                             | Function                                                |
| --------------------------------------------------------------------- | ------------------------------------------------------- |
| You own a long-lived session (Celery task, WebSocket handler, script) | `bind_scope_to_session(db, org, user, project)`         |
| Short project-scope window inside a FastAPI request                   | `with temporary_project_scope(db, org, user, project):` |
| Re-apply GUCs after a mid-request `db.commit()` (no context manager)  | `set_session_variables(db, org, user, project)`         |

**Why the distinction matters.** `bind_scope_to_session` writes `db.info['_scope']`, which activates
the ORM auto-filter for the session's remaining lifetime. Calling it inside a FastAPI request for a
temporary project window leaks the project filter into every subsequent query on that session —
queries silently return empty results or wrong counts with no error raised.

`temporary_project_scope` saves and restores both `db.info['_scope']` and the RLS GUCs for its
block. Any `db.commit()` inside the block (which triggers the `after_begin` re-apply listener) uses
the temporary project scope, not the caller's original scope. Safe to use repeatedly within a single
request session.

`bind_scope_to_session` callers (sessions they own outright):

- `jobs/execution/batch/context.py`
- `celery/signals.py`
- `jobs/telemetry/evaluate.py`
- `jobs/telemetry/post_ingest.py`
- `jobs/execution/executors/data.py`
- `routers/parameters.py`
- `services/telemetry/conversation_linking.py`
- `services/websocket/handlers/architect.py`

`temporary_project_scope` callers (in-request, short project windows):

- `services/organization.py` (three sites — onboarding endpoint/project seeding)

`set_session_variables` callers (explicit GUC-only re-apply):

- `routers/organization.py` (re-applies GUCs after mid-request `db.commit()` during onboarding)

### GUC reset ordering invariant

`set_config(..., is_local=true)` GUCs are transaction-scoped and the pool rolls back on check-in,
so blanking them is "belt-and-suspenders". The hazard is **timing**: never blank the org/project
GUCs while ORM changes are still unflushed. A deferred write flushed under a blank
`app.current_organization` makes the strict `tenant_isolation` policy reject the `''::uuid` cast
(`invalid input syntax for type uuid: ""`). `get_db_with_tenant_variables` therefore commits
deferred writes _before_ `reset_session_context()` runs. Any new side-channel caller that resets or
blanks GUCs must commit/flush first.

## Usage attribution (LLM token accrual)

`MODEL_TOKENS` accrual is automatic. There is nothing to wire at a call site, and adding one is
not supposed to require thinking about billing.

- **Emission**: `app/utils/usage_tracking.py` registers one process-wide sink with the SDK at
  startup (FastAPI lifespan, Celery `worker_process_init`). Every model built anywhere in the
  process reports to it.
- **Who to bill**: read at emission time from `app/usage_attribution.py`'s ContextVar, bound by
  the `bind_usage_attribution` async dependency (pulled in by `get_tenant_db_session`) and by the
  Celery `task_prerun` handler.
- **Whether to skip**: `BaseLLM.usage_metered`, stamped by the model-resolution layer via
  `stamp_usage_provenance`. When `USAGE_QUOTAS_ENABLED` is true (Rhesis cloud), a `metered=False`
  model is skipped: the org supplied its own API key and pays the provider directly. When quotas
  are off (self-hosted, the default), every model accrues regardless so the usage page shows the
  full picture of what the instance spent.

Two rules for new code:

1. **Resolve models through `app/utils/user_model_utils.py`.** A bare `get_model("provider/name")`
   produces an unstamped model, which bills the org and logs `usage.unstamped_model` so the call
   site can be found and fixed.
2. **Hand work to a thread with `with_usage_attribution(fn)`** if you use `ThreadPoolExecutor` or
   `run_in_executor`. Neither copies contextvars; `asyncio.to_thread` and `anyio.to_thread` do,
   and need nothing.

Usage that arrives with no org bound is logged as `usage.unattributed` rather than dropped —
a nonzero rate there means a code path is missing its binding.

## Affordances — backend side

The backend resolves permitted actions per object and exposes them as `permitted_actions: string[]`
on response schemas that mixin `WithPermittedActions`. See `apps/frontend/AGENTS.md` for the full
three-primitives frontend contract.

Adding affordances to a new resource: add `WithPermittedActions` to the Pydantic response schema
and annotate `resource_type` on the class. Key files: `schemas/affordances.py` (mixin),
`auth/capabilities.py` (`Permission` enum, keep in sync with frontend `Capability` enum).

## Feature Gating

Gated capabilities (e.g. SSO) flow through a single primitive on the backend and a mirrored one on
the frontend. No ad-hoc `if` checks scattered across routers or components.

- `app/features/__init__.py` — the `FeatureRegistry`, `Feature` dataclass, `FeatureName` str-Enum,
  and `LicenseProvider` protocol. `DefaultLicenseProvider` is the stub used today; a real one
  installs via `FeatureRegistry.set_license_provider(...)` when licensing lands.
- `app/features_bootstrap.py` — declarative list of features, called once from `main.py` lifespan.
- `app/auth/feature_gates.py` — FastAPI dependencies `require_feature` (404 on denial, no
  enumeration leak) and `has_feature` (bool for branching).
- `app/routers/features.py` — `GET /features` returns license info and enabled feature names.

Community features are never registered. `FeatureRegistry` is for EE features only; if a
capability ships in `apps/backend/` under MIT, it is unconditionally available and needs no gating.

### Adding a new EE feature

1. Add a member to `FeatureName` in `app/features/__init__.py`.
2. Implement the feature under `ee/backend/src/rhesis/backend/ee/<feature>/`.
3. Register it in `ee/backend/src/rhesis/backend/ee/__init__.py:bootstrap()` by calling
   `FeatureRegistry.register(Feature(...))` with an optional `runtime_check`, then
   `app.include_router(...)` for any new endpoints.
4. Gate routes with `Depends(require_feature(FeatureName.X))`. Use
   `FeatureRegistry.is_available(name, org)` for org-aware checks elsewhere and
   `FeatureRegistry.is_registered(name)` for early-bailout checks before an org has been resolved
   (e.g. inside an OIDC callback).
5. Mirror the name in `apps/frontend/src/constants/features.ts` and wrap the UI in
   `<FeatureGate feature={FeatureName.X}>` — see `apps/frontend/AGENTS.md`.

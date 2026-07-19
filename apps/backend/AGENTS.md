# Backend Rules

FastAPI REST API with Celery task processing. Layered: routers → services → models/crud.
See root `AGENTS.md` for repo-wide rules (commits, PRs, testing overview, tech stack).

## Directory layout

- `src/rhesis/backend/app/` — FastAPI core: `models/` (SQLAlchemy ORM), `schemas/` (Pydantic),
  `routers/`, `services/` (business logic), `auth/`, `scope.py`/`models/scope_events.py` (tenant
  scope), `features/` (feature gating)
- `alembic/` — DB migrations
- `tasks/` — Celery background tasks (`execution/`, `telemetry/`)
- `metrics/` — evaluation metrics (DeepEval, RAGAS, native providers)

## Testing

Backend tests must run from `apps/backend` — its `pyproject.toml` sets
`testpaths = ["../../tests/backend"]` and `pythonpath = ["src"]`, so paths/imports only resolve
from that directory. Never run `uv run pytest tests/backend/...` from the repo root.

```bash
cd apps/backend
uv run pytest ../../tests/backend/ -v
# single test class:
uv run pytest ../../tests/backend/services/explorer/test_tests.py::TestCreateExplorerTestSet -v
```

## Debugging

When asked to debug the backend, add this to the end of
`src/rhesis/backend/app/main.py` and run it directly (don't lint-check or mention it in chat):

```python
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rhesis.backend.app.main:app", host="0.0.0.0", port=8080, reload=True, log_level="debug")
```

## Ambient Request Scope (Tenant Filtering & Stamping)

All tenant context (`organization_id`, `user_id`, `project_id`) is stored **once per request** on
`Session.info['_scope']` by `get_db_with_tenant_variables()` and automatically applied by two
SQLAlchemy event listeners — no explicit threading through router, service, or CRUD parameters is
needed.

> **Note:** The `ContextVar` (`_scope`) is **not** used for normal FastAPI/Celery request paths.
> It is only for scripts and tests that call `bind_scope()` explicitly. Do **not** call
> `current_scope()` from inside a request handler and expect it to reflect the active project —
> use `db.info.get('_scope')` instead.

### How it works

`scope.py` defines:

- `RequestScope` — frozen dataclass holding the identity triple
- `_scope: ContextVar[RequestScope]` — for scripts/tests via `bind_scope()` only; **not** set on
  the normal request path
- `_tenant_filter_disabled: ContextVar[bool]` — separate bypass flag

`models/scope_events.py` registers two listeners:

- `auto_filter` (`Query.before_compile`) — adds `WHERE organization_id=...` (and `project_id=...`)
  to every SELECT, UPDATE, DELETE automatically
- `auto_stamp` (`Session.before_flush`) — fills `organization_id`, `user_id`, `project_id` on new
  ORM objects when the column is `None`

### Using the scope

```python
# Normal FastAPI route — nothing extra to do. Scope is bound by get_db_with_tenant_variables.

# Admin / cross-org read:
from rhesis.backend.app.scope import bypass_tenant_filter
with bypass_tenant_filter():
    all_rows = db.query(SomeModel).all()  # filter skipped; stamp still active

# Per-query bypass (legacy Query API only):
query._bypass_scope = True

# Background scripts / migrations (scope is unbound outside get_db_with_tenant_variables):
from rhesis.backend.app.scope import RequestScope, bind_scope, reset_scope
token = bind_scope(RequestScope(organization_id="...", user_id="..."))
try:
    ...
finally:
    reset_scope(token)
```

### Limitations (Phase 0 — document, not fix)

- `db.execute(select(...))` / `db.scalars(...)` (ORM 2.0 style) are **not** auto-filtered by the
  `before_compile` listener. Use `db.query(...)` instead, or add explicit `organization_id` filters.
  RLS (Phase 5) is the security backstop for those paths.
- `Session.bulk_insert_mappings` / `bulk_save_objects` bypass `before_flush`; auto-stamp does **not**
  fire. Include `organization_id`/`user_id`/`project_id` in bulk payloads manually.
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

- `tasks/execution/batch/context.py`
- `celery/signals.py`
- `tasks/telemetry/evaluate.py`
- `tasks/telemetry/post_ingest.py`
- `tasks/execution/executors/data.py`
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

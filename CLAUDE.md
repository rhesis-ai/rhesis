# Rhesis Project Rules

## Technology Stack

### Backend
- **Language**: Python 3.10+
- **Package Manager**: uv with pyproject.toml
- **Validation**: Pydantic 2.x
- **Testing**: pytest

### Python SDK
- **Language**: Python 3.10+
- **Package Manager**: uv with pyproject.toml
- **Validation**: Pydantic 2.x
- **Testing**: pytest

---

## Python Code Quality

### Ruff Linting and Formatting

Run ruff checks and formatting **only before pushing** (e.g. before `git push` or creating a pull request):

```bash
# Check for linting issues
uvx ruff check <path/to/file.py>

# Auto-format the code
uvx ruff format <path/to/file.py>

# Check again to verify
uvx ruff check <path/to/file.py>
```

Run ruff only when preparing to push or open a PR, not after every Python file change.

### Fixing Line Length Issues

If ruff reports line length violations (E501), fix them by:

1. Breaking long strings into multiple lines
2. Breaking long f-strings
3. Breaking long function calls

Maximum line length: 100 characters

---

## Local Development

### UV Package Manager
1. Always use uv to manage Python projects
2. Execute uv command in the root of the projects (SDK, Backend)
3. Use `uv add <package>` to install dependencies
4. Use `uv test` to run tests
5. Use `uv run <script>` to run scripts

### Backend Debugging
When debugging, add the following at the end of `apps/backend/src/rhesis/backend/app/main.py`:
```python
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rhesis.backend.app.main:app", host="0.0.0.0", port=8080, reload=True, log_level="debug")
```

### GitHub CLI
Use GitHub CLI whenever possible. If a GitHub link is pasted, use GitHub CLI to open it.

---

## Testing

### SDK Tests

1. Tests are stored in `<project_root>/tests/sdk` directory
2. Run unit tests:
```bash
cd sdk
make test
```

3. Run integration tests (starts backend):
```bash
cd sdk
make test-integration
```

4. Check backend logs:
```bash
cd sdk
docker compose -f ../tests/docker-compose.test.yml --profile sdk logs sdk-test-backend
```

5. Run single tests:
```bash
cd sdk
uv run pytest ../tests/sdk/integration/test_entities.py::test_endpoint
```

---

## Git Commits

### Pre-Commit Workflow

1. Check current status:
```bash
git status
git diff
```

2. Review and analyze changes - group by:
   - Feature additions
   - Bug fixes
   - Refactoring
   - Documentation updates
   - Configuration changes
   - Test modifications

3. Stage changes strategically (avoid `git add .`):
```bash
git add <file1> <file2>
git add -p <filename>  # Stage parts of files
```

### Conventional Commits

Format:
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types:
- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Formatting changes (no code meaning change)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvement
- **test**: Adding or correcting tests
- **build**: Build system or dependency changes
- **ci**: CI configuration changes
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

Rules:
1. Use lowercase for type and description
2. No period at the end of the description
3. Use imperative mood ("add" not "adds" or "added")
4. Limit description to 50 characters or less
5. Use scope to specify component (e.g., `feat(auth): add login validation`)
6. Use `BREAKING CHANGE:` in footer for breaking changes

Examples:
- `feat: add user authentication`
- `fix(api): resolve timeout issue in user endpoint`
- `docs: update installation guide`
- `feat!: remove deprecated API endpoints` (! indicates breaking change)

---

## Pull Requests

### Core Principles

1. **Write Small PRs**: Easier to review, less bugs, clearer history
2. **One Logical Change Per PR**: Avoid mixing unrelated changes

### Branch Creation
```bash
git fetch origin
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### PR Title Guidelines
- Use clear, descriptive titles
- Start with action verb (Add, Fix, Update, Remove)
- Keep under 72 characters

### PR Description Template
```markdown
## Purpose
[Explain why this change is needed]

## What Changed
- [Key change 1]
- [Key change 2]

## Additional Context
- [Links to issues, tickets]
- [Breaking changes or migration notes]

## Testing
[How to test these changes]
```

### Size Guidelines
- **Ideal**: 1-200 lines
- **Acceptable**: 200-400 lines
- **Large**: 400+ lines (break down if possible)

---

## GitHub Issues

When creating issues:
1. Use appropriate template (Bug, Feature, or Task) from `.github/ISSUE_TEMPLATE`
2. Use GitHub CLI: `gh issue create`
3. List existing labels: `gh label list` and select appropriate ones (don't add issue type labels)
4. Keep issues short and to the point
5. Ask user for confirmation before creating

---

## Documentation (docs/ directory)

### Framework
Nextra for documentation (MDX files).

### Critical Rules

**Escape Curly Braces**: MDX interprets `{...}` as JSX expressions.
```mdx
✅ GOOD: API PUT /test_results/\{id\}
❌ BAD:  API PUT /test_results/{id}
```

**When NOT to escape**:
- Inside code blocks (fenced with ```)
- Inside inline code with backticks

### Style Guidelines
- Remove decorative emojis (use "Note:", "Warning:", "Tip:" instead)
- Follow existing documentation style
- Include code examples with language tags
- Test that documentation builds without errors

### Material-UI Icons in MDX
Never import `@mui/icons-material/*` directly in `.mdx` files. Create a JSX component in `/docs/src/components/` and register it in `/docs/src/mdx-components.js`.

---

## Codebase Structure

### Backend (`apps/backend/`)
FastAPI-based REST API with Celery task processing.

Key directories:
- `src/rhesis/backend/app/` - FastAPI application core
  - `models/` - SQLAlchemy ORM models
  - `schemas/` - Pydantic request/response schemas
  - `routers/` - FastAPI route handlers
  - `services/` - Business logic layer
  - `auth/` - Authentication & authorization
- `alembic/` - Database migrations
- `tasks/` - Celery background tasks
- `metrics/` - Evaluation metrics

Key patterns:
- Layered Architecture: routers → services → models/crud
- Multi-tenancy: Organization-based data isolation
- Background Processing: Celery tasks for test execution
- Feature Gating: `FeatureRegistry` in `app/features/` is the single
  place to check whether a gated capability is available for an
  organization. See "Feature Gating" below.

### SDK (`sdk/`)
Python SDK for interacting with Rhesis platform.

Key directories:
- `src/rhesis/sdk/`
  - `client.py` - Main RhesisClient
  - `entities/` - API entity wrappers
  - `decorators/` - `@endpoint` and `@observe` decorators
  - `connector/` - Bidirectional connector for test execution
  - `metrics/` - Evaluation metrics
  - `models/` - LLM model providers
  - `synthesizers/` - Test data generation
  - `telemetry/` - OpenTelemetry integration

Key patterns:
- Entity Pattern: Pythonic wrappers for API resources
- Provider Pattern: Pluggable LLM and metric providers
- Decorator Pattern: `@endpoint` and `@observe` for instrumentation

### Frontend (`apps/frontend/`)
Next.js 14+ with App Router and Material UI.

Key directories:
- `src/app/` - Next.js App Router pages
  - `(protected)/` - Authenticated routes
- `src/components/` - Shared components
  - `common/` - Reusable UI components
- `src/utils/api-client/` - Backend API clients
- `src/hooks/` - Custom React hooks

Key patterns:
- App Router: File-based routing with layouts
- Route Groups: `(protected)` for authenticated routes
- Dynamic Routes: `[identifier]` for entity pages
- Feature Gating: `FeaturesProvider` + `useFeature` / `<FeatureGate>`
  consume `GET /features` to conditionally render gated UI. See
  "Feature Gating" below.

---

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

`apps/backend/src/rhesis/backend/app/scope.py` defines:

- `RequestScope` — frozen dataclass holding the identity triple
- `_scope: ContextVar[RequestScope]` — for scripts/tests via `bind_scope()` only; **not** set on
  the normal request path
- `_tenant_filter_disabled: ContextVar[bool]` — separate bypass flag

`apps/backend/src/rhesis/backend/app/models/scope_events.py` registers two listeners:

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

| Situation | Function |
|---|---|
| You own a long-lived session (Celery task, WebSocket handler, script) | `bind_scope_to_session(db, org, user, project)` |
| Short project-scope window inside a FastAPI request | `with temporary_project_scope(db, org, user, project):` |
| Re-apply GUCs after a mid-request `db.commit()` (no context manager) | `set_session_variables(db, org, user, project)` |

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
deferred writes *before* `reset_session_context()` runs. Any new side-channel caller that resets or
blanks GUCs must commit/flush first.

---

## Feature Gating

Gated capabilities (e.g. SSO) flow through a single primitive on the
backend and a mirrored one on the frontend. No ad-hoc `if` checks
scattered across routers or components.

### Backend

- `apps/backend/src/rhesis/backend/app/features/__init__.py` -- the
  `FeatureRegistry`, `Feature` dataclass, `FeatureName` str-Enum, and
  `LicenseProvider` protocol. `DefaultLicenseProvider` is the stub
  used today; a real one installs via
  `FeatureRegistry.set_license_provider(...)` when licensing lands.
- `apps/backend/src/rhesis/backend/app/features_bootstrap.py` --
  declarative list of features, called once from `main.py` lifespan.
- `apps/backend/src/rhesis/backend/app/auth/feature_gates.py` --
  FastAPI dependencies `require_feature` (404 on denial, no
  enumeration leak) and `has_feature` (bool for branching).
- `apps/backend/src/rhesis/backend/app/routers/features.py` --
  `GET /features` returns license info and the enabled feature names.

### Frontend

- `apps/frontend/src/constants/features.ts` -- `FeatureName` mirror of
  the backend enum. Keep in sync when adding features.
- `apps/frontend/src/contexts/FeaturesContext.tsx` -- `FeaturesProvider`
  (mounted in the protected layout), `useFeature(name)`, and
  `<FeatureGate feature={...}>`. Fail-closed: features are `false`
  during the initial fetch and on error.
- `apps/frontend/src/utils/api-client/features-client.ts` -- typed
  client for `GET /features`.

### Adding a new EE feature

Community features are never registered. The `FeatureRegistry` is for EE
features only; if a capability ships in `apps/backend/` under MIT, it is
unconditionally available and needs no gating.

1. Add a member to `FeatureName` in
   `apps/backend/src/rhesis/backend/app/features/__init__.py`.
2. Implement the feature under `ee/backend/src/rhesis/backend/ee/<feature>/`.
3. Register it in `ee/backend/src/rhesis/backend/ee/__init__.py:bootstrap()`
   by calling `FeatureRegistry.register(Feature(...))` with an optional
   `runtime_check`, then `app.include_router(...)` for any new endpoints.
4. Gate routes with `Depends(require_feature(FeatureName.X))`. Use
   `FeatureRegistry.is_available(name, org)` for org-aware checks elsewhere
   and `FeatureRegistry.is_registered(name)` for early-bailout checks
   before an org has been resolved (e.g. inside an OIDC callback).
5. Mirror the name in `apps/frontend/src/constants/features.ts` and wrap
   the UI in `<FeatureGate feature={FeatureName.X}>`.

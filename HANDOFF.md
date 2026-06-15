# Handoff: `feat/project-container` — All Phases Complete

**Branch:** `feat/project-container`
**Workspace:** `/Users/harry/rhesis/worktrees/rhesis/feat/project-container`

---

## What has been done

All phases through Phase 5 are complete. The full test suite is green (**4,284 passed, 0 failures**).

| Phase | What was built |
|---|---|
| 0 | `RequestScope` ContextVar + `scope_events.py` (auto-filter + auto-stamp SQLAlchemy listeners) |
| 1 | `ProjectMembership` model; auto-enrol org creator + invitees |
| 2 | `ProjectMixin` applied to 31 models; Alembic migration `a1b2c3d4e5f0` adds `project_id` columns + `project_membership` table |
| 2.5 | `project_id: Optional[UUID4] = None` on base Pydantic schemas; stripped from update payloads (`_prepare_update_data`) |
| 3 | `get_project_context` FastAPI dep (resolves `X-Project-Id` header → token → None, validates membership); threaded into `get_tenant_db_session`; `X-Project-Id` documented in OpenAPI via `Header()` annotation |
| 4 | `has_project_id()` + `with_project_filter()` in `query_utils.py`; `validate_same_project()` cross-project guard in `crud_utils.py` |
| 4.5 | `task_launcher()` forwards `project_id` in Celery headers |
| 5 | RESTRICTIVE `project_isolation` RLS policies on 36 scoped tables (`c3d4e5f6a7b2`) |
| 5+ | Backfill missing `tenant_isolation` on 14 tables; `project_isolation` on 4 pre-existing tables; auto-RLS event trigger (`d4e5f6a7b8c3`) |

**Database state:** both dev (`rhesis-db`) and test DB at port 10000 are stamped at `d4e5f6a7b8c3 (head)`.

**Migration chain:** `alembic upgrade head` runs cleanly from an empty database (verified on a fresh instance).

---

## Phase 5 details

### Migration `c3d4e5f6a7b2` — RESTRICTIVE project_isolation

Added `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and a `RESTRICTIVE project_isolation` policy to 36 tables (31 entity + 4 association + `architect_message`). Token excluded by design.

```sql
CREATE POLICY project_isolation ON <table>
    AS RESTRICTIVE
    FOR ALL
    USING (
        project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
        OR project_id IS NULL
        OR current_setting('app.current_project', true) = ''
    );
```

### Migration `d4e5f6a7b8c3` — Backfill gaps + auto-RLS event trigger

1. **Backfilled `tenant_isolation`** on 14 tables that were added after the original RLS migration and never received a policy: `architect_session`, `auth_client`, `behavior_metric`, `chunk`, `comment`, `embedding`, `file`, `metric`, `model`, `project_membership`, `task`, `test_set_metric`, `tool`, `trace`.

2. **Backfilled `project_isolation`** on 4 tables with pre-existing `project_id` columns that Phase 5 did not cover: `endpoint`, `experiment`, `project_membership`, `trace`.

3. **Installed `auto_apply_rls_policies()` event trigger** — fires on `CREATE TABLE` and `ALTER TABLE`, automatically applying `tenant_isolation` and/or `project_isolation` policies when `organization_id` / `project_id` columns are detected. Exempt tables: `token`, `user`, `organization`, `refresh_token`, `alembic_version`.

### Migration chain fix

Fixed 5 pre-existing data migrations that imported live ORM models, causing `alembic upgrade head` to fail on a fresh database (the SELECT included `project_id` before it existed):
- `8a2f3b4c5d6e` — replaced with raw SQL `UPDATE`
- `6a7b8c9d0e1f` — added raw SQL `EXISTS` guard
- `41a9355b3991` — upgrade check + downgrade converted to raw SQL
- `e8dd05d20cd0` — same
- `554e3e207a3f` — downgrade converted to raw SQL

---

## RLS coverage

After `d4e5f6a7b8c3`, every table with `organization_id` has a `tenant_isolation` PERMISSIVE policy and every table with `project_id` has a `project_isolation` RESTRICTIVE policy, except for deliberately exempt tables.

### Exempt tables

| Table | Reason |
|---|---|
| `token` | Queried before tenant context is bound during authentication |
| `user` | Identity table; cross-org lookups required |
| `organization` | Has its own dedicated RLS policy |
| `refresh_token` | Auth infrastructure; no tenant columns |
| `alembic_version` | Schema management |

### Verifying RLS coverage

Gap check — should return zero rows when all policies are in place:

```sql
SELECT c.table_name, c.column_name AS has_column, 'MISSING POLICY' AS status
FROM information_schema.columns c
LEFT JOIN pg_policies p
  ON p.tablename = c.table_name
  AND p.policyname = CASE c.column_name
    WHEN 'organization_id' THEN 'tenant_isolation'
    WHEN 'project_id' THEN 'project_isolation'
  END
WHERE c.column_name IN ('organization_id', 'project_id')
  AND c.table_schema = 'public'
  AND c.table_name NOT IN ('token', 'user', 'organization', 'refresh_token', 'alembic_version')
  AND p.policyname IS NULL
ORDER BY c.table_name;
```

Expected output: only `v_test_result_stats` and `v_test_run_stats` (views, not tables — RLS does not apply to views; they inherit RLS from their underlying tables).

---

## Auto-RLS event trigger

New tables automatically receive RLS policies. No manual migration step required.

- `CREATE TABLE` with `organization_id` → `tenant_isolation` (PERMISSIVE) auto-created
- `CREATE TABLE` with `project_id` → `project_isolation` (RESTRICTIVE) auto-created
- `ALTER TABLE ADD COLUMN project_id` → `project_isolation` auto-created
- Exempt tables (`token`, `user`, `organization`, `refresh_token`, `alembic_version`) are skipped
- Reentry-safe: uses a transaction-local GUC (`auto_rls.active`) to prevent infinite recursion from the trigger's own `ALTER TABLE ENABLE ROW LEVEL SECURITY` calls

---

## Phase 4 helpers

### `query_utils.py`

- **`has_project_id(model)`** — mirrors `has_organization_id`; returns `True` if the model has a `project_id` column.
- **`QueryBuilder.with_project_filter(project_id)`** — applies `project_id = :pid OR project_id IS NULL`. Use only in admin/cross-scope paths; the ambient listener handles normal requests automatically.

### `crud_utils.py`

- **`validate_same_project(*entities)`** — raises `ValueError` when two or more ORM instances have conflicting non-NULL `project_id` values. Call before creating cross-entity associations (e.g. adding a test to a test set from a different project). NULL `project_id` (org-wide entity) is always compatible.

---

## Bulk / raw-SQL audit

`rg` sweep of `apps/backend/src/` for `bulk_insert_mappings`, `bulk_save_objects`, and `connection.execute(` found **no hits in application code** — only in Alembic data-migration files where ORM bypass is intentional and the rows written are schema-level data, not tenant entities.

Conclusion: no remediation needed. The caveat (auto-stamp does not fire on bulk paths) is documented in `scope.py` and `scope_events.py` for future reference.

---

## Key files

| File | Purpose |
|---|---|
| `apps/backend/src/rhesis/backend/app/scope.py` | `RequestScope` dataclass + ContextVar + `bypass_tenant_filter()` |
| `apps/backend/src/rhesis/backend/app/models/scope_events.py` | Auto-filter + auto-stamp SQLAlchemy listeners |
| `apps/backend/src/rhesis/backend/app/dependencies.py` | `get_project_context` (with OpenAPI `X-Project-Id` docs), `get_tenant_db_session` |
| `apps/backend/src/rhesis/backend/app/models/project_membership.py` | ProjectMembership ORM model |
| `apps/backend/src/rhesis/backend/app/utils/query_utils.py` | `has_project_id()`, `QueryBuilder.with_project_filter()` |
| `apps/backend/src/rhesis/backend/app/utils/crud_utils.py` | `validate_same_project()` cross-project guard |
| `apps/backend/src/rhesis/backend/alembic/versions/a1b2c3d4e5f0_*.py` | Phase 2 migration — `project_id` columns + `project_membership` table |
| `apps/backend/src/rhesis/backend/alembic/versions/c3d4e5f6a7b2_*.py` | Phase 5 migration — RESTRICTIVE `project_isolation` RLS policies |
| `apps/backend/src/rhesis/backend/alembic/versions/d4e5f6a7b8c3_*.py` | Phase 5+ migration — backfill + auto-RLS event trigger |
| `apps/backend/src/rhesis/backend/app/database.py` | `get_db_with_tenant_variables` (sets RLS vars + binds RequestScope) |

---

## Known limitations / deferred work

### Auto-filter is `before_compile`-only — `select()` reads are uncovered

`auto_filter` in `scope_events.py` is a `Query.before_compile` listener. It covers every
`db.query(...)` call (the dominant pattern) including `.update()` / `.delete()`. It does **not**
fire for `db.execute(select(...))` / `db.scalars(...)` (ORM 2.0 style).

There is currently no `db.execute(select(...))` usage on tenant tables in app code, so this is a
theoretical gap. RLS (Phase 5, migrations `c3d4e5f6a7b2` + `d4e5f6a7b8c3`) backstops all tenant
tables regardless of the filtering path. Tracked in [#1846](https://github.com/rhesis-ai/rhesis/issues/1846).

### Deferred embedding jobs are project-scoped

`_queue_embedding_after_commit` captures `target.project_id` into the job payload (NULL when the
parent entity is org-wide). `_process_pending_embedding_jobs` passes it to
`get_db_with_tenant_variables(org, user, project_id)` so the ambient auto-stamp listener
correctly scopes each `Embedding` row to its parent entity's project. Org-wide entities
(`project_id = NULL`) produce org-wide embeddings, which pass the `project_isolation` RLS policy
and the `with_project_filter()` predicate as expected.

---

## Running the test suite

```bash
cd /Users/harry/rhesis/worktrees/rhesis/feat/project-container/apps/backend
RHESIS_SKIP_MIGRATIONS=1 PATH=/opt/homebrew/bin:/usr/local/bin:$PATH \
  uv run --extra cpu --extra all pytest ../../tests/backend/ \
  -p no:warnings --tb=short -q \
  --ignore=../../tests/backend/ee --ignore=../../tests/backend/integration
```

---

## Running migrations

```bash
cd apps/backend/src/rhesis/backend
DB_HOST=localhost DB_NAME=rhesis-db APP_DB_USER=rhesis-user APP_DB_PASS=rhesis-password \
  uv run --project /Users/harry/rhesis/worktrees/rhesis/feat/project-container/apps/backend \
  alembic -c alembic.ini upgrade head
```

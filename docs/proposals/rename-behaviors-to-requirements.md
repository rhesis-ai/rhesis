# Rename Behaviors → Requirements: implementation plan

**Status:** Decisions locked, ready to implement
**Date:** 2026-07-20, revised 2026-08-12
**Inventory verified against:** `main` at `d5d4b11d0`
**Scope:** Database, backend, frontend, SDK, MCP, agent skill, Penelope, docs, tests, deployment config

Supersedes the phased, compatibility-first draft. That version proposed seven releases with dual
API paths and alias removal at the end. Review feedback rejected that shape (see decision record
below), and a second audit found the footprint is roughly twice what the first inventory listed.

---

## Decision record

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Single atomic cutover**, not a phased rollout | Behavior is chained through org bootstrap seed data → Garak taxonomy (backend *and* SDK copies) → MCP tool contract → stats/insights. A deprecation window means holding two vocabularies in sync across that chain for months, and the failure mode is a wrong label, not a crash, so drift sits unnoticed. |
| 2 | **DB Option B folded in** (rename tables, columns, views, policies, functions) | Deferring it means the ORM maps `Requirement` onto table `behavior` indefinitely, and every raw-SQL site keeps the old name. Two migrations for one end state. |
| 3 | **No aliases, no dual-read, no redirects on the API** | `/behaviors` has no external announcement or SLA. Building a compatibility layer in one release and tearing it out in another is cost with no consumer. |
| 4 | **Frontend `/behaviors` → `/requirements` keeps a permanent redirect** | Cheap, one line, and users have bookmarks. This is the one exception to #3: it is a UI route, not an API contract. |
| 5 | **Entity *values* are not renamed** | `Reliability`, `Robustness`, `Compliance` are referenced **by name** from `initial_data.json`, `garak/taxonomy.py`, and `garak/detectors.yaml`. The entity is renamed; its instances are not. |
| 6 | Stored historical values get a **data migration**, not dual-read | Enumerated in "Stored data" below. Every one is a backfill in the same Alembic revision as the schema rename. |

### Vocabulary collision to resolve first

The word "requirements" is **already in use** for a different thing:

- `skills/rhesis/references/requirements-workflow.md` is titled "Requirements → test foundation"
  and means *turn a PRD into behaviors*.
- `docs/content/docs/agent-skill/requirements.mdx` is the "Requirements workflow" page, same
  meaning.

After the rename, "build requirements from your requirements" is incoherent. Pick one:

- **(recommended)** Rename the *input* concept to **spec** / **PRD** throughout the skill and docs
  (`spec-workflow.md`, "Spec → test foundation"), freeing "Requirement" for the entity.
- Or keep "requirements workflow" for the input and accept the overload.

This decision blocks the docs and skill work packages and nothing else, so it does not gate the
start of implementation.

---

## Size and shape

| Measure | Count |
|---------|-------|
| Files containing `behavio` (excluding `node_modules`, build output) | **701** |
| Matching lines | **~6,540** |
| Of those, in migrations + changelogs (frozen, not edited) | ~200 |

Re-measured against `main` at `d5d4b11d0`. Two structural changes on main since the first audit
materially affect this plan:

- **`app/crud.py` is now the package `app/crud/`.** `crud/behavior.py` is an additional file
  rename; `crud/metric.py` (61 refs) carries the M2M logic. The single 105-reference file no longer
  exists.
- **The explorer JSONB marker is already migrated.** `test_set.explorer_row` is a real boolean
  column (migration `7dd69fe35db5_add_explorer_row_to_test_set_and_test.py`), `explorer/tests.py`
  reads that column, and `ADAPTIVE_TESTING_BEHAVIOR` is gone from the backend entirely. This
  removes what was the sharpest silent-failure risk in the earlier revision of this plan. There is
  a migration test suite at `tests/backend/alembic/` to model the cutover's own tests on.

This cannot be a 400-line PR. The honest shape is:

1. **Prep PRs** (mergeable independently, each behavior-preserving and small).
2. **One atomic cutover PR** containing the Alembic revision plus everything that must move with
   it. This one is large by necessity: it is not splittable without a broken intermediate state.
3. **Follow-up PRs** for surfaces that do not affect runtime correctness (docs prose, notebooks,
   examples).

---

## What is NOT renamed

This list is the allowlist for the final verification sweep. Anything matching `behavio` outside it
after the cutover is a miss.

**English "behavior", unrelated to the entity**

- `tests/backend/metrics/test_evaluator_behavior.py` and evaluator orchestration test names
- Soft-delete / proxy / cookie / scope-listener wording in comments and docstrings
  (`models/soft_delete_events.py`, `docs/content/contribute/backend/soft-deletion.mdx`)
- `apps/backend/Dockerfile` ("env-flipped behavior")
- `apps/frontend/Makefile` ("mimics the validation script behavior")

**Third-party or generated text we do not own**

- `apps/worker/k8s/hpa-example.yaml` — `behavior:` is the Kubernetes HPA API field
- `apps/telemetry-processor/alembic.ini` — Alembic's own generated comment
- `.github/ISSUE_TEMPLATE/bug_report.md` — "Expected Behavior" / "Actual Behavior" headings

**History, which must stay accurate**

- All `CHANGELOG.md` files (root, `apps/*`, `sdk/`), `docs/content/changelog.mdx`,
  `docs/sphinx/source/changelog/*.rst`
- Existing Alembic revisions under `alembic/versions/` (the new revision renames; old ones stay as
  written)

**Entity instance values**

- `Reliability`, `Robustness`, `Compliance`, `Adaptive Testing`

**Open call**

- `apps/frontend/src/config/test-templates.yml` prompt text ("Generate test behaviors for AI bias
  detection…"). This English steers LLM output that lands in the entity, so it probably should
  change, but it is prompt tuning, not a rename. Recommend changing it and re-running
  `apps/frontend/scripts/generate-templates.js` rather than hand-editing
  `test-templates.generated.ts`.
- Metric prompt English ("refusal behavior", "forbidden behaviors") in
  `sdk/src/rhesis/sdk/metrics/providers/native/templates/`,
  `sdk/src/rhesis/sdk/synthesizers/assets/base.jinja`,
  `sdk/src/rhesis/sdk/synthesizers/multi_turn/templates/base.jinja`,
  `penelope/src/rhesis/penelope/prompts/templates/system_prompt.j2`. Changing these changes model
  output. Treat as a separate, evaluated change, not part of the rename.

---

## Inventory

### 1. Database

A table rename in Postgres does **not** rewrite the bodies of functions, and does not rename policy
names, index names, constraint names, or view output column aliases. Each has to be handled
explicitly.

| Object | Where | Action |
|--------|-------|--------|
| Tables `behavior`, `behavior_metric` | `models/behavior.py`, `models/metric.py` | `ALTER TABLE ... RENAME` |
| Columns `test.behavior_id`, `prompt.behavior_id`, `response_pattern.behavior_id`, `behavior_metric.behavior_id` | `models/test.py:55`, `models/prompt.py:46`, `models/response_pattern.py:17`, `models/metric.py:24` | `ALTER TABLE ... RENAME COLUMN` |
| FK / PK / index names embedding `behavior` | Introduced across `7bacdb1ce615`, `a7e1303a11da`, `c607e92437c5`, `a1b2c3d4e5f0` | `ALTER ... RENAME CONSTRAINT` / `ALTER INDEX ... RENAME` |
| Stats views selecting `t.behavior_id` and `b.name AS behavior_name` | created in `cb4b107b5daf_add_stats_views.py`, mapped by `models/stats_views.py:52,61` | **DROP and CREATE.** The output alias `behavior_name` is baked into the view definition and does not follow a table rename. |
| Stats-view performance indexes | `5b3d40e898ff_add_performance_indexes_for_stats_views.py` | Rename or recreate with the views |
| RLS policies on `behavior` / `behavior_metric` | `7bacdb1ce615`, `c3d4e5f6a7b2`, `b8c9d0e1f2a3`, `d4e5f6a7b8c3`; reference copy in `alembic/row_level_security.sql` (9 refs to `public.behavior`) | Policies follow the table, **policy names do not**. Also update the reference `.sql`. |
| Auto-RLS trigger table list | `d4e5f6a7b8c3_backfill_rls_gaps_and_auto_rls_trigger.py:30` | Rename in the list |
| `delete_user_and_organization_data` PL/pgSQL function | `alembic/delete_user_and_organization_data.sql` (hardcoded table-name array line 22; `DELETE FROM behavior_metric` / `DELETE FROM behavior` lines 206-217; `behavior_id IN (SELECT id FROM behavior …)` line 107) installed by `bcf762626378` | **`CREATE OR REPLACE FUNCTION` with the new body.** A table rename leaves this function referencing a table that no longer exists, and it only fails at org-deletion time. |
| Legacy data-migration SQL | `alembic/migrate_tests.sql` | Update or delete if dead |
| Raw SQL in application code | `app/services/annotations.py:103-186` — `LEFT JOIN behavior b ON b.id = tst.behavior_id`, aliases `behavior_id` / `behavior_name`, search over `COALESCE(behavior_name, '')` | Hand-edit. No ORM rename touches this. |

### 2. Stored data (requires backfill, not just code changes)

This is the category that breaks silently. Each item is a row-level `UPDATE` in the same revision.

| Stored value | Location | Consequence if missed |
|---|---|---|
| `type_lookup` row with `type_value = 'Behavior'` | seeded from `app/services/initial_data.json`; consumed by tags, comments, `EntityType.BEHAVIOR` (`app/constants.py:15`, `app/schemas/tag.py:33`, FE `types/entity-type.ts:21`) | Tag and comment assignment on the entity stops resolving |
| `permission` catalog rows `behavior:create|read|update|delete` | seeded by `5b6c7d8e9f0a_seed_rbac_permission_catalog.py:59-62`; enum in `app/auth/capabilities.py:197-201` | Users lose all access to the entity. **`UPDATE permission SET name = …` in place**, never delete-and-insert: built-in roles compute their sets from code and follow the enum rename automatically, but custom roles have `role_permission` rows keyed on `permission.id`, and recreating the row orphans every custom grant. The drift guard at `tests/backend/security/test_capability_catalog.py` catches a code/catalog mismatch but not orphaned grants. |
| `architect_session.plan_data` JSONB with keys `behaviors`, `behavior_metric_mappings`, `behavior` | `models/architect.py:20`; shape defined by `sdk/.../architect/plan.py` (`BehaviorSpec` at 27, `behavior_metric_mappings` at 211) | Every saved Architect session fails to deserialize. Renaming the Pydantic fields without backfilling `plan_data` is a hard break. **This is now the sharpest silent-failure path.** |
| `MetricsSource.BEHAVIOR = 'behavior'` | `app/schemas/test_set.py:14`, FE `interfaces/test-configuration.ts:12` | Stored test-configuration rows stop matching; `TestDetailMetricsTab.tsx:116,146,151` falls through to the wrong branch |
| Stats mode `behavior` and metric key `behavior_pass_rates` | `app/schemas/stats.py`, `app/services/stats/test_result.py`, SDK `entities/stats.py:27` | Insights renders empty |
| Preflight check id `behavior_metric_coverage` | `app/services/preflight/constants.py:6`, used by `checks.py:719`, `orchestrator.py:174`, displayed by FE `components/common/PreflightDialog.tsx` | Check disappears from the preflight dialog |
| SDK `PlanCategory.BEHAVIOR = 'behavior'` | `sdk/.../architect/tool_registry.py:22,44` | Architect tool routing misfires |

Write the backfill as **idempotent** `UPDATE`s guarded on the old value, so a re-run after a partial
failure is safe.

### 3. Backend code

Renames (file + symbols): `app/models/behavior.py`, `app/routers/behavior.py`,
`app/schemas/behavior.py`.

Heaviest touch points by reference count:

| File | Refs | Note |
|---|---|---|
| `app/crud/metric.py` | 61 | M2M association logic |
| `app/crud/behavior.py` | 47 | File rename |
| `app/crud/test_run.py`, `crud/__init__.py`, `crud/explorer.py`, `crud/comment.py` | 23 total | |
| `app/mcp_server/mcp_tools.yaml` | 97 | See "public contracts" |
| `app/services/preflight/checks.py` | 43 | Coverage check logic |
| `app/services/initial_data.json` | 41 | `type_value: "Behavior"`, 3 default entity rows, ~25 metrics referencing them by name, and `"behaviors"` arrays on metric records |
| `app/services/garak/taxonomy.py` | 39 | ~30 `behavior="Robustness"/"Compliance"/"Reliability"` literals feeding `sync.py`, `importer.py`, `dynamic.py`. Kwarg renames; values stay. |
| `app/services/test.py` | 35 | Bulk create/extraction path |
| `app/services/organization.py` | 27 | Org bootstrap; reads `"behaviors"` key at line 904 |
| `app/routers/metric.py` | 23 | Nested M2M routes |
| `app/services/explorer/tests.py` | 19 | JSONB marker read/write |
| `app/services/test_execution.py` | 16 | |
| `app/services/test_run.py`, `app/routers/test_result.py` | 15 each | |
| `alembic/utils/metric_sync.py` | 15 | Reads `"behaviors"` from metric seed JSON; used by Garak metric migrations such as `c2d3e4f5a6b7` |
| `app/services/test_set.py`, `app/schemas/test.py` | 14 each | |
| `app/services/test_config_generator.py` | 13 | Paired with `app/templates/test_config_generator.jinja2` (7 refs): the prompt and its output parser must change together |
| `app/services/test_generation_pipeline.py` | 12 | |
| `app/services/annotations.py` | 11 | Raw SQL, see above |
| `app/services/file_import/mapping.py` | 11 | CSV column contract; paired with `mapping_prompt.jinja` (4 refs), `validators.py`, `builder.py` |
| `app/utils/crud_utils.py` | 10 | |
| `tasks/execution/metrics_utils.py` (`get_behavior_metrics`), `tasks/execution/executors/data.py` (11), `tasks/test_set.py` | | Celery paths, outside routers and services |
| `app/routers/base.py:25`, `app/routers/resolve.py`, `app/routers/__init__.py`, `app/routers/garak.py`, `app/routers/services.py`, `app/routers/explorer.py`, `app/routers/test.py`, `app/routers/test_set.py`, `app/routers/test_run.py` | | Route registration and nested paths |

Also: `models/organization.py`, `status.py`, `test_set.py`, `prompt.py`, `test.py`, `metric.py`,
`response_pattern.py`, `stats_views.py`, `__init__.py` (relationship names and the
`behavior_metric_association` export), `app/services/bulk_defaults.json`,
`app/services/prompt.py`, `app/schemas/services.py`, `app/schemas/__init__.py`,
`app/schemas/stats.py`.

`app/services/explorer/tests.py` still has 19 references, but they are entity references now, not
the JSONB marker. The marker moved to `test_set.explorer_row` on main.

EE backend has no entity references (the `behavio` hits in `ee/backend/` are unrelated English).

### 4. Public contracts beyond REST

**MCP server** (`app/mcp_server/`). This is a tool surface consumed by external AI agents and
deserves the same weight as the REST rename:

- 7 production tools in `mcp_tools.yaml`: `list_behaviors`, `get_behavior`, `create_behavior`,
  `update_behavior`, `add_behavior_to_metric`, `remove_behavior_from_metric`,
  `get_metric_behaviors`
- A hardcoded `entity_type: "Behavior"` constraint on tag assignment
- Planning-prompt text in `server.py:81-85` ("Creation order: behaviors → metrics → …")
- Response schema examples embedding `"behavior": "behavior name"`

**SDK.** `sdk/src/rhesis/sdk/entities/behavior.py` (file rename), `entities/__init__.py:13,41-42`
(`Behavior`, `Behaviors` exports), `clients/api.py:25` (`Endpoints.BEHAVIORS = "behaviors"`),
`entities/test.py` (`_push_required_fields`, field validators), `entities/test_set.py` (20 refs,
CSV `fieldnames`), `entities/test_result.py`, `entities/stats.py`, `synthesizers/base.py`,
`synthesizers/synthesizer.py`, `synthesizers/owasp_synthesizer.py`,
`synthesizers/multi_turn/base.py`, `synthesizers/config_synthesizer.py`,
`metrics/providers/garak/registry.py` + `detectors.yaml` (23 refs, the parallel copy of the
taxonomy), `metrics/providers/garak/detector_metric.py`, `connector/types.py`,
`adaptive_testing/_test_tree.py`, `telemetry/integrations/langchain/integration.py`.

**SDK Architect** is the tightest coupling in the repo: `agents/architect/agent.py` (65 refs,
including `_BEHAVIOR_TOOLS` at 1119 which hardcodes MCP tool names) and
`agents/architect/plan.py` (41 refs, the persisted plan schema), plus prompt templates
`telemachus-save-plan.j2`, `telemachus-guidelines.j2`, `telemachus-security.j2`,
`telemachus-resolution.j2`, `workflow-routing.j2`, `streaming_response.j2`, `iteration_prompt.j2`.
`_BEHAVIOR_TOOLS` and `mcp_tools.yaml` must land in the same commit or Architect silently stops
recognizing entity tool calls.

**OData filter contract.** Navigation property names come from ORM relationship names, so
`$filter=behavior/name eq 'X'` becomes `$filter=requirement/name eq 'X'`. Documented in
`docs/content/contribute/backend/odata-guide.mdx` (39 refs).

### 5. Frontend

Route tree `src/app/(protected)/behaviors/` moves to `requirements/` (12 files), plus a permanent
redirect per decision #4.

Files outside that tree, by weight:

| File | Refs |
|---|---|
| `app/(protected)/metrics/components/MetricsDirectoryTab.tsx` | 117 |
| `components/common/SelectBehaviorsDialog.tsx` (+ its test, 64) | 50 |
| `app/(protected)/test-runs/[identifier]/components/TestDetailMetricsTab.tsx` | 61 |
| `app/(protected)/metrics/components/MetricsClient.tsx` | 45 |
| `app/(protected)/test-runs/[identifier]/components/TestRunStatsTab.tsx` | 44 |
| `app/(protected)/metrics/[identifier]/MetricDetailPageTabs.tsx` | 44 (hardcodes `router.push('/behaviors')`) |
| `app/(protected)/tests/components/UpdateTest.tsx` / `CreateTest.tsx` | 42 / 18 |
| `utils/api-client/behavior-client.ts` (+ test) | 40 |
| `app/(protected)/tests/new-manual/components/ManualTestWriter.tsx` | 40 |
| `app/(protected)/insights/*` (utils, hooks, 8 components) | ~200 total |
| `app/(protected)/test-sets/new-generated/components/TestGenerationFlow.tsx` | 30 |
| `app/(protected)/test-runs/[identifier]/*` (7 files) | ~150 total |

Cross-cutting definitions that must move together:

- `constants/capabilities.ts` (`Capability.Behavior.*`) **and** `ee/frontend/src/rbac/capability-groups.ts`. These are independent copies.
- `constants/query-keys.ts:19` — `behaviorKeys = createEntityKeys('behaviors')`. A partial rename fragments the React Query cache with no error.
- `utils/api-client/config.ts:27` — `behaviors: '/behaviors'`
- `utils/api-client/metrics-client.ts:87,99,113` and `test-runs-client.ts:94` — nested paths built by hand
- Four interfaces shaping the data: `interfaces/behavior.ts`, `interfaces/test-results.ts`, `interfaces/metric.ts`, `interfaces/tests.ts`
- `types/entity-type.ts:21` — `BEHAVIOR: 'Behavior'`
- `interfaces/test-configuration.ts:12,22` — `MetricsSource.BEHAVIOR`
- `components/BehaviorsIcon.tsx` + the `components/icons.ts:134` barrel export
- `constants/entity-empty-state-types.ts:39` (`'behaviors'` union member) and `constants/entity-empty-state-env.ts:75,77`
- Shared components keyed on entity names: `components/common/PreflightDialog.tsx`, `DeletedEntityAlert.tsx`, `BaseTag.tsx`, `FilterDrawer.tsx`, `DetailTabPanel.tsx`, `components/comments/CommentsSection.tsx`
- `hooks/useLookups.ts` (9 refs)
- `config/test-templates.yml` → regenerate `test-templates.generated.ts` via `scripts/generate-templates.js`; do not hand-edit the generated file

**Deployment config, outside the repo.** `NEXT_PUBLIC_BEHAVIORS_EMPTY_STATE_VIDEO_URL` and
`NEXT_PUBLIC_BEHAVIORS_EMPTY_STATE_ARTICLE_URLS` are set in the deploy environment. Renaming them
in code without updating GitHub Actions / Cloud Run / Vercel silently blanks the empty state. Add
this to the release checklist explicitly.

### 6. Agent skill and Penelope

Neither appears in the original inventory.

**`skills/rhesis/`** is published and installed by users (`npx skills add rhesis-ai/rhesis`).
21 files, ~200 refs. `references/tool-catalog.md` (41 refs) mirrors the MCP tool names and must
move with `mcp_tools.yaml`. `references/prd/behavior-design.md` is a file rename.
`references/requirements-workflow.md` is the vocabulary collision above. Also
`references/entity-model.md`, `use-case-bracketfeld.md`, `result-analysis.md`, `definitions.md`,
`odata-patterns.md`, `metric-scope.md`, `insights-summary.md`, `workflow-index.md`,
`phases/{reuse,creation,planning,direct-requests,analysis}.md`,
`prd/{scope-alignment,prd-anatomy,metric-design}.md`, `SKILL.md`, `README.md`.

**`penelope/`** is a separate package: 19 files. `src/rhesis/penelope/prompts/templates/system_prompt.j2`
(19 refs), `prompts/agent/turn_prompts.py`, `prompts/tools/tool_descriptions.py`,
`prompts/agent/default_instructions.py`, `agent.py`, `strategies/domain_probing.py`, plus 9 files
under `examples/`. Most of Penelope's usage is prompt English about model behavior, so triage
carefully: only the parts naming the Rhesis entity change.

### 7. Docs

| Surface | Refs | Note |
|---|---|---|
| `content/contribute/backend/odata-guide.mdx` | 39 | Filter examples, a user-facing contract |
| `content/glossary/glossary-terms.jsonl` | 35 lines | Structured glossary data, separate from the MDX pages |
| `content/sdk/entities/test-attributes.mdx` | 29 | |
| `content/contribute/backend/test-result-stats.mdx` | 20 | |
| `content/guides/testing-user-journeys.mdx` | 19 | |
| `content/docs/behaviors/` | 16 | Directory rename |
| `content/glossary/behavior/index.mdx` | 3 | Directory rename, cross-referenced from the `metric`, `tag`, `explorer`, and `synthesizer` glossary entries |
| `src/public/diagrams/user-journey.excalidraw` | 15 | Diagram asset; needs re-export, not a text edit |
| `src/components/PlatformStructureMap.jsx`, `PlatformFeatures.jsx` | 9 | |
| `sphinx/source/rhesis.entities.rst:44,47` | | `.. autoclass:: rhesis.sdk.entities.Behavior`. Breaks the SDK API docs build if missed. |
| `content/docs/_meta.tsx:96` | | `behaviors: 'Behaviors'` sidebar label |
| `src/next.config.mjs` | | **No `/behaviors` redirect exists.** Add one; this is new content, not an edit. |
| `content/docs/agent-skill/requirements.mdx`, `for-agents.mdx` | 17 | Vocabulary collision |
| ~30 more `.mdx` pages | | `docs/`, `sdk/`, `architect/`, `explorer/`, `test-sets/`, `test-runs/`, `tests/`, `metrics/`, `concepts.mdx` |

API docs are hand-written MDX, not generated from OpenAPI, so nothing auto-propagates.

Repo-level docs: root `README.md`, `RELEASING.md`, `HANDOFF.md`, `apps/frontend/AGENTS.md`,
`docs/decluttering-rules.md`, `docs/rhesis-docs-navigation-overhaul-work-packages.md`,
`sdk/README.md`, `penelope/README.md`, `penelope/CONTRIBUTING.md`, `ee/backend/README.md`.

`examples/*.ipynb` (5 notebooks) have behavior data in committed cell outputs. Follow-up PR; a
stale notebook output is not a correctness problem.

### 8. Tests and tooling

`tests/sdk/integration/conftest.py:303,326` runs `TRUNCATE TABLE metric, behavior, model CASCADE`.
Raw SQL against the physical table name. Update in the cutover PR or every integration run fails.

`tests/k6/common.js:56` registers a load-test endpoint `{ name: 'auth_behaviors', path: '/behaviors/' }`,
documented in `tests/k6/README.md:11`. Load tests will 404 after the cutover, which reads as a
performance regression rather than a rename miss.

`tests/backend/alembic/` (`test_idempotency.py`, `test_explorer_row_migration.py`) is the pattern to
follow for the cutover revision's own tests. `test_explorer_row_migration.py` is a worked example of
testing a JSONB-to-column data migration, which is close to what the `plan_data` backfill needs.

`scripts/check_organization_filtering.py` (multi-tenancy audit tooling) hardcodes `'Behavior'`
at line 33 and regexes `Behavior\.organization_id` at 90 and `behavior_id\s*==` at 175. If missed
it does not fail, it just stops auditing the renamed entity.

Shared test infrastructure, where a careless edit affects other entities:

- `tests/backend/routes/conftest.py` — parametrized fixture shared across behavior, topic,
  category, metric, and dimension
- `tests/backend/routes/fixtures/factory_fixtures.py` (79), `data_factories.py` (36),
  `factories.py` (21), `endpoints.py` (28), `README.md` (64)

Renames: `tests/backend/routes/test_behavior.py` (115),
`tests/backend/routes/fixtures/entities/behaviors.py`,
`tests/backend/crud/test_behavior_metric_security.py` (68),
`apps/frontend/tests/e2e/tests/behaviors.spec.ts` + `behaviors-crud.spec.ts`,
`apps/frontend/tests/e2e/pages/BehaviorsPage.ts`, `apps/frontend/tests/e2e/fixtures/behaviors.json`.

High-count non-rename test files: `tests/sdk/agents/test_architect.py` (135),
`tests/backend/utils/test_soft_delete_crud.py` (125),
`test_soft_delete_querybuilder.py` (116), `tests/backend/routes/test_response_pattern.py` (111),
`test_comment.py` (104), `tests/backend/utils/test_scope_listeners.py` (82),
`tests/backend/services/test_test_execution.py` (79), `tests/backend/crud/test_metric_crud.py` (71),
`tests/backend/routes/test_recycle.py` (64), plus ~40 more.

---

## Execution plan

### Prep PRs (small, independent, merge first)

Each is behavior-preserving and reviewable on its own. None of them renames the entity.

| # | PR | Size | Why first |
|---|----|------|-----------|
| P1 | Resolve the vocabulary collision: rename the skill/docs "requirements workflow" input concept to "spec" | ~150 lines | Unblocks docs and skill work; meaningless to review mid-rename |
| P2 | Extract every hardcoded `'/behaviors'`, `'behaviors'`, and `'Behavior'` string literal in the frontend into the existing constants modules (`api-client/config.ts`, `query-keys.ts`, `types/entity-type.ts`) | ~200 lines | Shrinks the cutover diff and makes the remaining sites greppable |
| P3 | Same for the backend: route prefix, resource name, and entity-type literals behind `app/constants.py` | ~150 lines | Same |
| P4 | Add a regression test asserting `architect_session.plan_data` round-trips through `TestPlan`, modelled on `tests/backend/alembic/test_explorer_row_migration.py` | ~60 lines | The remaining silent-failure path. Prove it works **before** touching it. Halved from the earlier revision: the explorer-filter half is unnecessary now that main uses `test_set.explorer_row`. |

### The cutover PR

One PR, one Alembic revision, ordered commits inside it:

1. **Alembic revision** (schema + data in one revision, downgrade implemented and tested)
   - `ALTER TABLE` / `RENAME COLUMN` / `RENAME CONSTRAINT` / `ALTER INDEX`
   - `DROP` + `CREATE` stats views and their indexes
   - Rename RLS policies
   - `CREATE OR REPLACE FUNCTION` for `delete_user_and_organization_data`
   - Idempotent backfills: `type_lookup`, `permission` (updated in place),
     `architect_session.plan_data`, `test_configuration` metrics source, any persisted stats or
     preflight payloads
   - `down_revision` set to the current head on `main` at the time of opening
2. **Backend**: models, schemas, routers, CRUD, services, tasks, raw SQL in `annotations.py`,
   permission enum, constants, seed JSON, Garak taxonomy kwargs, Jinja prompt templates + parsers
3. **MCP** `mcp_tools.yaml` + `server.py` **and** SDK `_BEHAVIOR_TOOLS` in the same commit
4. **SDK**: entities, clients, synthesizers, Garak provider, Architect plan schema and templates
5. **Frontend**: route tree move + redirect, clients, interfaces, query keys, capabilities (both
   copies), insights, shared components, regenerated templates
6. **Tests**: renames, fixture updates, `tests/sdk/integration/conftest.py` raw SQL,
   `tests/k6/common.js` endpoint path, plus a migration test under `tests/backend/alembic/`
7. **Tooling**: `scripts/check_organization_filtering.py`, `alembic/row_level_security.sql`,
   `alembic/migrate_tests.sql`
8. **Docs that describe contracts**: `odata-guide.mdx`, `test-result-stats.mdx`, SDK entity pages,
   `sphinx/source/rhesis.entities.rst`, `_meta.tsx`, the new `next.config.mjs` redirect

### Follow-up PRs

- Remaining docs prose, glossary MDX + `glossary-terms.jsonl`, the Excalidraw re-export
- `skills/rhesis/` and `penelope/` prompt text triage
- `examples/*.ipynb` re-run
- Metric prompt English, if the team decides to change it

### Release checklist (not in any diff)

- Rename `NEXT_PUBLIC_BEHAVIORS_EMPTY_STATE_VIDEO_URL` and `..._ARTICLE_URLS` in every deploy
  environment, in the same window as the frontend deploy
- Migrate before deploying app code (the schema rename is not backward-compatible with the old
  code, so this is a maintenance-window deploy, not a rolling one)
- SDK major version bump with migration notes

---

## Verification gates

The plan is only as good as the sweep that proves it complete. All of these are cheap to run.

**1. Source sweep.** `rg -i behavio` across the repo returns only files on the "What is NOT
renamed" allowlist. Encode the allowlist as a script so it runs in CI for one release.

**2. Postgres catalog sweep.** Renames leave debris in places `\dt` does not show:

```sql
SELECT relname FROM pg_class WHERE relname ILIKE '%behavio%';
SELECT policyname, tablename FROM pg_policies
  WHERE policyname ILIKE '%behavio%' OR qual ILIKE '%behavio%' OR with_check ILIKE '%behavio%';
SELECT indexname FROM pg_indexes WHERE indexname ILIKE '%behavio%' OR indexdef ILIKE '%behavio%';
SELECT viewname FROM pg_views WHERE viewname ILIKE '%behavio%' OR definition ILIKE '%behavio%';
SELECT proname FROM pg_proc WHERE prosrc ILIKE '%behavio%';        -- catches the delete-org function
SELECT conname FROM pg_constraint WHERE conname ILIKE '%behavio%';
SELECT tgname FROM pg_trigger WHERE tgname ILIKE '%behavio%';
SELECT column_name, table_name FROM information_schema.columns WHERE column_name ILIKE '%behavio%';
```

**3. Row-level assertions**, run against a restored production snapshot:

```sql
SELECT count(*) FROM type_lookup WHERE type_value = 'Behavior';                    -- 0
SELECT count(*) FROM permission WHERE name LIKE 'behavior:%';                      -- 0
SELECT count(*) FROM architect_session WHERE plan_data ? 'behaviors';              -- 0
SELECT count(*) FROM architect_session WHERE plan_data ? 'behavior_metric_mappings'; -- 0
-- and the inverse: every row that had the old key now has the new one
```

**4. Behavioral checks**

- Fresh-org bootstrap: seed an org, assert the three default entities exist by name and that Garak
  taxonomy sync maps onto them (proves seed data and taxonomy did not drift)
- Org deletion against a seeded org (proves the PL/pgSQL function was recreated)
- Insights page renders non-empty against restored data (proves stats views and the
  `requirement_pass_rates` key line up)
- Open a pre-migration Architect session (proves the `plan_data` backfill)
- RBAC: a user with the old grants can still read and write the entity
- Preflight dialog shows the coverage check
- `scripts/check_organization_filtering.py` passes
- Docs build (`next build`) and Sphinx build both succeed
- Full backend, SDK, frontend unit, and Playwright E2E suites green

**5. Downgrade rehearsal.** Run `alembic downgrade` on a snapshot and re-run the row-level
assertions inverted. A rename migration without a tested downgrade has no rollback.

---

## Risks

| Risk | Mitigation |
|---|---|
| `delete_user_and_organization_data` still references the old table; fails only at org-deletion time | `pg_proc` sweep + org-deletion test |
| Saved Architect sessions fail to deserialize | P4 round-trip test written before the change, `plan_data` backfill, row assertion, and open a pre-migration session by hand |
| `tests/k6` load tests 404 on `/behaviors/`, read as a perf regression | Endpoint path updated in the cutover PR |
| `_BEHAVIOR_TOOLS` and `mcp_tools.yaml` drift, so Architect stops recognizing tool calls | Same commit, plus an Architect integration test |
| Custom-role grants orphaned by recreating instead of updating `permission` rows in place | `UPDATE ... SET name`, keep the id; assert `role_permission` count unchanged before and after |
| Stats view output alias `behavior_name` survives the table rename and quietly breaks insights | DROP/CREATE views, `pg_views` sweep, insights render check |
| Env vars renamed in code but not in the deploy environment | Release checklist item, verified in staging first |
| Over-renaming prompt English changes model output | Prompt text is explicitly out of the cutover PR |
| The cutover PR is too large to review carefully | Prep PRs shrink it; ordered commits within the PR let reviewers go layer by layer; the verification gates carry the load that line-by-line review cannot |

---

## Still open

1. Vocabulary collision: "spec" for the PRD input, or accept the overload? (P1 blocker only)
2. `test-templates.yml` prompt English: change and regenerate, or leave?
3. Metric prompt English: separate evaluated change, or leave indefinitely?
4. Maintenance window: the schema rename is not backward-compatible with old app code, so confirm
   we can take a short downtime rather than a rolling deploy.

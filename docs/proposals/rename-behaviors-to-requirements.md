# Proposal: Rename Behaviors → Requirements

**Status:** Draft — seeking feedback  
**Author:** Platform team  
**Date:** 2026-07-20  
**Scope:** Backend, Frontend, SDK, MCP, Docs, DB (optional), Permissions

This is a **proposal only**. No product code is renamed in this PR. Please comment on the open questions before we start implementation.

---

## Motivation

“Behavior” is a first-class domain entity on the platform (tests link to it; metrics associate via M2M). Product and customer language increasingly prefer **Requirements** as the clearer term for what users define and evaluate against.

We want a deliberate, compatibility-first rename across UI, API, SDK, and (optionally) the database — not a big-bang search-and-replace.

---

## Current footprint (inventory summary)

| Area | Approx. domain refs | Notes |
|------|---------------------|--------|
| Backend `app/` | ~900+ | Model, router `/behaviors`, CRUD, stats, preflight |
| Frontend `src/` | ~1,500+ | Routes `/behaviors`, clients, insights, nav |
| SDK | ~350+ | `Behavior` / `Behaviors`, Architect plan fields |
| Tests | ~1,000+ | Route, CRUD, e2e, fixtures |
| Docs | ~70 files | `docs/content/docs/behaviors/` |
| EE | RBAC labels only | `capability-groups.ts` |

**Database**

- Tables: `behavior`, `behavior_metric`
- FKs: `test.behavior_id`, `prompt.behavior_id`, `response_pattern.behavior_id`
- Stats views: `behavior_id`, `behavior_name`

**API**

- Primary: `POST/GET/PUT/DELETE /behaviors`, metrics sub-routes
- Related: `/metrics/{id}/behaviors`, `/test_runs/{id}/behaviors`, stats `mode=behavior`

**Permissions**

- `behavior:read|create|update|delete` (backend + frontend + EE RBAC)

**No feature gate** exists for this entity. Renaming is a breaking API/DB/SDK change unless we keep aliases.

There is **no existing `Requirement` entity**, so the name is free. Scattered English uses of “requirement” in comments/prompts are unrelated and must not be blindly replaced.

---

## What must not be renamed

Do **not** treat every “behavior” string as the entity:

- Soft-delete / proxy / cookie “behavior”
- Evaluator orchestration tests (e.g. `test_evaluator_behavior.py`)
- Metric/prompt English (“refusal behavior”, “forbidden behaviors”) — decide case by case
- Historical changelog entries
- Unrelated English “requirement” in auth/preflight comments

---

## Recommended strategy: phased, compatibility-first

```text
Labels → API dual paths → Code/SDK rename → DB rename (optional) → Remove aliases
```

| Phase | What | Breaking? | Ship when |
|-------|------|-----------|-----------|
| **0** | Lock glossary, DB strategy, deprecation window | No | Before coding |
| **1** | UI + docs labels only (“Requirements”) | No | First |
| **2** | Dual API `/requirements` + keep `/behaviors`; FE routes + redirects | Soft | After Phase 0 decisions |
| **3** | Permissions `requirement:*` + migrate role grants; dual-accept | Soft | With Phase 2 |
| **4** | Backend/FE symbol & file rename (ORM may still map to old tables) | Internal | After dual API |
| **5** | SDK major: `Requirement` + deprecated `Behavior` aliases | Soft major | After dual API live |
| **6** | Optional DB rename (`behavior` → `requirement`, FKs, views, RLS) | Hard | Separate milestone |
| **7** | Remove aliases after deprecation window | Yes | After notice period |

### PR slicing (implementation, later)

Keep PRs reviewable (~1–400 lines where possible):

1. Backend dual routes + schemas aliases  
2. Permissions catalog + role migration  
3. Stats / preflight / `MetricsSource` dual-read + data migration  
4. Frontend routes, clients, pages + redirects  
5. MCP tools rename + aliases  
6. SDK major + Architect plan dual-read  
7. Docs + skills  
8. (Optional) DB rename + RLS/views  

---

## Open decisions (please comment)

### 1. Physical database names

- **Option A (recommended for first release):** Keep tables `behavior` / `behavior_metric` and columns `behavior_id`. Rename Python/API/UI only. Lowest risk; lingering DB name.
- **Option B:** Rename tables/columns in Alembic + RLS + stats views in the same program. Cleaner long-term; highest risk and rollback cost.

**Proposal:** A now, B as a follow-up once API/SDK have settled.

### 2. Deprecation window

How long do we keep `/behaviors`, SDK `Behavior`, and old permission/string enums?

**Proposal:** At least one major SDK release / ~N months of dual support, then remove in a follow-up.

### 3. Product language consistency

Confirm “Requirements” everywhere domain means the entity, including:

- Nav and page titles  
- Insights (“by requirement”)  
- “Requirement metrics” / Architect “requirement specs”  
- Import column preferred name `requirement` (with `behavior` alias)

### 4. Stored string values

Existing JSON / TypeLookup / comments may store `"behavior"`, `entity_type="Behavior"`, `MetricsSource.BEHAVIOR`, `use_behavior`, test-set metadata `behaviors`.

**Proposal:** Dual-read (accept old + new) for one major version; migrate writers to new values; optional backfill migration for historical rows.

---

## Compatibility matrix (target shape)

| Old | New | Transition |
|-----|-----|------------|
| `/behaviors` | `/requirements` | Dual routes; deprecate old |
| Nested `.../behaviors` | `.../requirements` | Same |
| `behavior:*` permissions | `requirement:*` | Migrate grants; dual-accept |
| SDK `Behavior` / `Behaviors` | `Requirement` / `Requirements` | Alias + deprecate |
| CSV/JSON column `behavior` | `requirement` | Accept both |
| Stats `mode=behavior` | `mode=requirement` | Dual-read |
| `MetricsSource.BEHAVIOR` | `REQUIREMENT` | Dual-read; migrate writers |
| Comment `entity_type=Behavior` | `Requirement` | Dual-read; migrate writers |
| FE `/behaviors` | `/requirements` | Redirect |

---

## Risks

1. **Stats views + RLS** break if a DB rename misses a policy or helper script.  
2. **RBAC rows** leave users unable to manage Requirements if permission strings flip without migration.  
3. **Historical test-run / test-set JSON** stops matching on a hard enum cutover.  
4. **Architect / MCP / Garak** mappings use Behavior *names* as strings — renames must stay intentional.  
5. Over-renaming English “behavior” in prompts dilutes meaning and creates noisy diffs.

---

## Success criteria

- Users see **Requirements** in UI and docs.  
- Existing API/SDK clients keep working through the deprecation window.  
- Permissions continue to authorize correctly after migration.  
- No silent breakage of stats, comments, imports, or Architect plans.  
- Clear public migration notes for SDK/API consumers.

---

## Out of scope for this proposal PR

- Any code rename  
- Alembic migrations  
- SDK release  
- Changing production data  

---

## Feedback requested

Please comment on this PR with:

1. Preference on **DB Option A vs B** (and timing for B if deferred)  
2. Preferred **deprecation window** length  
3. Any product language exceptions (places that should keep “behavior”)  
4. Whether external/API customers need a formal announcement before Phase 2  
5. Anything missing from the inventory or phase plan  

Once decisions are locked, we can open an epic and Phase 1 (labels-only) as the first implementation PR.

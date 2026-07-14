# Workflow index

Read this file first when routing a request. Do **not** answer platform mechanics from memory — open the listed references before planning or creating.

---

## Shared skeleton (every full workflow)

```
resolve by name → list_behaviors + list_metrics once → plan → user approval → create in order → optional execute → analyze
```

Creation order: behaviors → metrics (with metric_scope) → mappings → tags (if planned) → generate_test_set → verify.

Details: `phases/creation.md`, `entity-model.md`, `metric-scope.md`.

---

## Route by user intent

| Intent | Read first | Then | Skip |
|---|---|---|---|
| Vague `/rhesis` or "help me test" | This file → `SKILL.md` intake | Matching path below | — |
| Named endpoint + explore/test | `phases/discovery.md` | `exploration-strategies.md` → `phases/planning.md` | PRD workflow |
| Pasted PRD / spec / FRs | `prd-workflow.md` | `use-case-bracketfeld.md` (target shape) → `metric-scope.md` | `explore_endpoint` unless user asks |
| "Run tests" / "analyze" / "compare runs" | `phases/execution.md` → `phases/analysis.md` | `result-analysis.md` | New plan |
| Single action ("list test sets", "fix metric X") | `phases/direct-requests.md` | `tool-catalog.md` if needed | Full phases |
| Entity / OData / tool questions | `definitions.md` | `entity-model.md`, `odata-patterns.md` | — |
| Terminology dispute | `definitions.md` | — | — |

---

## Context detection (before showing menu)

| Signal | Default path |
|---|---|
| PRD paste, numbered FRs, "requirements doc" | PRD foundation |
| Endpoint name + "test" / "explore" | Exploration (Quick unless they said comprehensive) |
| Test run id, "compare runs", "last run" | Run / analyze |
| OpenAPI, `AGENTS.md`, agent code in repo | Quick exploration of implied endpoint |
| None of the above | Four-path menu below |

## Four-path menu (ambiguous start)

When intent is unclear, present **one** menu and wait for the user's choice:

```text
What would you like to do?

1. Quick exploration — fast scan of an endpoint's domain and boundaries
2. Comprehensive exploration — full capability and boundary analysis
3. Build a test foundation from your PRD — behaviors, metrics, and test sets
4. Run or analyze existing tests — execute a test set or review/compare past runs
```

| Choice | Next |
|---|---|
| 1 Quick | `phases/discovery.md` → Quick strategy |
| 2 Comprehensive | `phases/discovery.md` → Comprehensive strategy |
| 3 PRD | `prd-workflow.md` — match `use-case-bracketfeld.md` |
| 4 Run / analyze | `phases/execution.md`, `phases/analysis.md` |

Skip the menu when intent is already clear. PRD and run/analyze paths skip exploration unless the user asks later.

**Write gate:** No `create_*` / `generate_*` until the user approves the plan.

---

## Reference catalog

| File | Contents |
|---|---|
| `definitions.md` | Platform vocabulary |
| `entity-model.md` | Entity graph and tool chains |
| `metric-scope.md` | Single-Turn vs Multi-Turn alignment |
| `prd-workflow.md` | PRD → test foundation pipeline |
| `use-case-bracketfeld.md` | **Golden example** — full plan shape (fictional PRD) |
| `exploration-strategies.md` | `explore_endpoint` strategies |
| `phases/discovery.md` | Discovery phase |
| `phases/planning.md` | Planning and reuse |
| `phases/creation.md` | Creation order and field constraints |
| `phases/execution.md` | Running tests |
| `phases/analysis.md` | Results and comparison |
| `phases/direct-requests.md` | One-off commands |
| `odata-patterns.md` | `$filter`, `$select`, batch lookups |
| `result-analysis.md` | Stats modes and presentation |
| `tool-catalog.md` | MCP tool listing |

---

## Grounding rule

Before citing **metric_scope**, **creation order**, **field constraints**, or **PRD extraction rules**, read the reference above — do not paraphrase from memory. For PRD plans, match the section structure in `use-case-bracketfeld.md`.

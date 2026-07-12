# Telemachus (Architect) parity plan

The **Rhesis agent skill** (`skills/rhesis/SKILL.md`) and **Telemachus** (native Architect in the web UI) are separate runtimes:

| | Agent skill | Telemachus |
|---|---|---|
| Instructions | `SKILL.md` + `references/` | `sdk/.../architect/prompt_templates/system_prompt.j2` |
| Tools | MCP over HTTP | `LocalToolProvider` + same `mcp_tools.yaml` |
| Write safety | Prompt + user approval | `save_plan`, Accept/Change UI, modes |

Telemachus does **not** load skill files today. This doc is the **port checklist** so both surfaces behave the same.

## 1. Four-path welcome menu (priority: high)

On ambiguous first message (no endpoint, no PRD paste, no run/analyze request), Architect should present:

```text
What would you like to do?

1. Quick exploration — fast scan of an endpoint's domain and boundaries
2. Comprehensive exploration — full capability and boundary analysis
3. Build a test foundation from your PRD — behaviors, metrics, and test sets
4. Run or analyze existing tests — execute a test set or review/compare past runs
```

**Skip menu** when intent is clear (same table as `SKILL.md` § Choose a workflow).

**Port target:** new `## Workflow routing` section in `system_prompt.j2`, before Discovery Phase.

**UI:** optional welcome chips in `ArchitectWelcome.tsx` matching the four labels.

## 2. PRD → test foundation workflow (priority: high)

Port from `references/prd-workflow.md` and `references/prd/*`:

- PRD intake (stakeholders, persona stories, numbered FRs)
- Fine-grained behavior splitting (`behavior-design.md`)
- AC-driven metrics (`metric-design.md`)
- `metric_scope` on every metric + test set alignment (`scope-alignment.md`)
- Tags via `list_tags` / `assign_tag` (after metrics, before `generate_test_set`)

**Port target:** `{% include "prd-workflow.j2" %}` or inline section in `system_prompt.j2`.

**Optional:** `AgentMode` for PRD in `tool_registry.py` so the mode chip shows the active workflow.

## 3. `metric_scope` + scope coverage (priority: critical) — **implemented**

Platform **drops** metrics whose `metric_scope` does not include the test's `test_type`.

**Done / in progress on this branch:**

- `plan.py` — `MetricSpec.metric_scope` + `save_plan` coverage validation
- `system_prompt.j2` — "Metric scope" section, planning + creation guidance
- `skills/rhesis/references/metric-scope.md` — shared when-to-use guide
- `docs/architect/planning.mdx` — user-facing scope section

**Remaining:**

- `PlanDisplay.tsx` — show scope column (optional)
- PRD workflow section in `system_prompt.j2` (separate from scope)

## 4. Plan schema extensions (priority: medium)

| Field | Model | Purpose |
|---|---|---|
| `tags` | `BehaviorSpec` | PRD tag taxonomy |
| `metric_scope` | `MetricSpec` | Run-time compatibility |
| `ac_source` | `MetricSpec` | FR/AC traceability |
| `target_metrics` | `TestSetSpec` | Metrics expected to run |

## 5. Already aligned (no port)

- Entity resolution ladder (Architect is richer)
- Creation order (behaviors → metrics → mappings → generate)
- `save_plan` + plan panel
- Quick / Comprehensive tool strategies (under exploration paths only)
- Execution / analysis / comparison sections
- `await_task` instead of manual polling

## 6. Implementation order

1. Four-path menu + workflow routing in `system_prompt.j2`
2. `metric_scope` in prompt + `create_metric` + `MetricSpec`
3. Scope coverage check in Planning Phase
4. PRD workflow section + file-attachment routing
5. `list_tags` / `assign_tag` in creation order
6. Plan schema + PlanDisplay UI
7. `ArchitectWelcome` chips + `docs/architect/scenarios.mdx`

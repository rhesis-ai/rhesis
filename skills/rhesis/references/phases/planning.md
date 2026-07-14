# Planning phase

Before proposing a plan:

1. `list_behaviors` with `$select=name,id,description` — once.
2. `list_metrics` with `$select=name,id,score_type,description,metric_scope` — once.
3. Reuse matches when intent aligns — mark **(reuse)**, **(improve)**, or **(new)**.

## Plan structure

- **Project** (optional — large new suites only)
- **Behaviors** with descriptions for new items
- **Test sets** — name, description, `num_tests`, `test_type`, behaviors, `generation_prompt`
- **Metrics** — criteria, thresholds, **`metric_scope`**
- **Mappings** — every behavior ≥1 metric
- **Scope coverage matrix** — see `metric-scope.md`

PRD plans: follow section list in `prd-workflow.md` and shape in `use-case-bracketfeld.md`.

## Reuse

Propose existing entities when they match. Say explicitly: "I'll reuse 'Refuses Harmful Requests'."

Skip project for ad-hoc work.

## Approval gate

Present plan in future tense. Wait for explicit yes before any create/generate call.

End with: "Does this look right? Shall I create this on Rhesis?"

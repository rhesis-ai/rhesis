# Terminology — confusions only

> **Canonical terms:** [Glossary](https://docs.rhesis.ai/glossary.md) — fetch `glossary/<id>.md` per term.
> Start with: `behavior`, `metric`, `metric-scope`, `test-set`, `endpoint`, `test`, `test-run`, `test-result`, `category`, `topic`, `tag`, `knowledge`.

Use this file when concepts get mixed up. Do **not** duplicate glossary definitions here.

---

## Common confusions

**Behavior vs metric** — Behavior = *what* should happen. Metric = *how* you measure it. Every behavior in a test set needs at least one linked metric before generation.

**Behavior vs category/topic** — Categories and topics organize tests. They do not replace behaviors or metrics. See glossary: `category`, `topic`, `behavior`.

**Single-Turn test vs metric scope** — A Multi-Turn test set only runs metrics with `"Multi-Turn"` in `metric_scope`. Plan both explicitly — see `metric-scope.md` and glossary `metric-scope`.

**PRD section title vs behavior** — "Security" or "Operate Safely" is not a behavior. Split numbered requirements and acceptance criteria into testable expectations (see `prd-workflow.md`).

**Source vs pasted PRD** — Pasted chat text is ephemeral. For large specs, `create_source` then pass the source id into `generate_test_set` (Single-Turn only). See glossary: `knowledge`.

**Endpoint vs MCP** — Endpoint = the AI app under test. MCP has two meanings: knowledge import vs Rhesis agent tool server. See glossary: `endpoint`, `mcp`.

---

## PRD traceability

| Term | Definition |
|---|---|
| **FR / AC** | Numbered functional requirement or acceptance criterion — primary source for **metrics**, not behavior titles. |
| **Assumption** | Something underspecified in the PRD that you infer; must be listed in the plan for user confirmation. |
| **TBD** | Requirement too vague to score — flag in plan; do not invent a numeric rubric. |

---

## Workflow terms (agent skill only)

| Term | Definition |
|---|---|
| **Scope coverage** | Every behavior in a test set must have ≥1 linked metric whose `metric_scope` includes that set's `test_type`. |
| **Generation prompt** | Text in `generate_test_set` `config` describing what the synthesizer should produce. |
| **Reuse** | Use an existing behavior/metric (`list_*` + same name) instead of creating a duplicate. |

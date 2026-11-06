# Terminology — confusions only

> **Canonical terms:** [Glossary](https://docs.rhesis.ai/glossary.md) — fetch `glossary/<id>.md` per term.
> Start with: `requirement`, `metric`, `metric-target`, `test-set`, `endpoint`, `test`, `test-run`, `test-result`, `category`, `topic`, `tag`, `knowledge`.

Use this file when concepts get mixed up. Do **not** duplicate glossary definitions here.

---

## Common confusions

**Requirement vs metric** — Requirement = *what* should happen. Metric = *how* you measure it. Every requirement in a test set needs at least one linked metric before generation.

**Requirement vs category/topic** — Categories and topics organize tests. They do not replace requirements or metrics. See glossary: `category`, `topic`, `requirement`.

**Test type vs metric target** — A test's type (Single-Turn or Multi-Turn) is how it runs. A metric's target is what it judges. A `conversation` target never runs on Single-Turn tests; every other target runs on both. See `metric-targets.md` and glossary `metric-target`.

**PRD section title vs requirement** — "Security" or "Operate Safely" is not a requirement. Split numbered requirements and acceptance criteria into testable expectations (see `spec-workflow.md`).

**Source vs pasted PRD** — Pasted chat text is ephemeral. For large specs, `create_source` then pass the source id into `generate_test_set` (Single-Turn only). See glossary: `knowledge`.

**Endpoint vs MCP** — Endpoint = the AI app under test. MCP has two meanings: knowledge import vs Rhesis agent tool server. See glossary: `endpoint`, `mcp`.

---

## PRD traceability

| Term | Definition |
|---|---|
| **FR / AC** | Numbered functional requirement or acceptance criterion — primary source for **metrics**, not requirement titles. |
| **Assumption** | Something underspecified in the PRD that you infer; must be listed in the plan for user confirmation. |
| **TBD** | Requirement too vague to score — flag in plan; do not invent a numeric rubric. |

---

## Workflow terms (agent skill only)

| Term | Definition |
|---|---|
| **Metric coverage** | Every requirement in a test set must have ≥1 linked metric that runs on that set's `test_type`. On a Single-Turn set, that means a metric whose target is not `conversation`. |
| **Generation prompt** | Text in `generate_test_set` `config` describing what the synthesizer should produce. |
| **Reuse** | Use an existing requirement/metric (`list_*` + same name) instead of creating a duplicate. |

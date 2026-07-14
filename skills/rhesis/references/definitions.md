# Rhesis platform definitions

> **Docs:** https://docs.rhesis.ai/docs/agent-skill/definitions.md

Canonical terms for this skill. When the user or your own draft mixes these up, align to these definitions.

---

## Core entities

| Term | Definition | Not the same as |
|---|---|---|
| **Endpoint** | The AI application under test — URL, request/response mapping, registered in a project. Tests execute against an endpoint. | Behavior, test set, MCP server |
| **Behavior** | One observable expectation the endpoint should meet (e.g. "Refuses Permit Fee Waivers"). Tags each **test** at generation time. | Category, topic, metric, test set name |
| **Metric** | How a test is **scored** — evaluation prompt, threshold or categories, and **`metric_scope`**. Linked to behaviors. | Behavior (what to test) vs metric (how to judge) |
| **Test set** | Named collection of generated or imported **tests**, with one `test_type` for all tests in the set. | Project, behavior list, metric |
| **Test** | One case inside a test set — a **prompt** (Single-Turn) or a **goal** (Multi-Turn). | Test run, test result |
| **Test run** | One execution of a test set against an endpoint. Produces test results. | Test set, test configuration |
| **Test result** | Outcome for one test in one run — status, metric scores, optional response text. | Metric definition |
| **Project** | Optional grouping for endpoints and large suites. Not required for ad-hoc testing. | Organization, test set |
| **Source** | Knowledge document on the platform used to ground **Single-Turn** test generation. | Tool connection (/tools), chat attachment |
| **Tag** | Org label on behaviors/metrics (`functional`, `safety`, etc.) via `assign_tag`. | Category, topic (test-set metadata) |

---

## Test shape

| Term | Definition |
|---|---|
| **Single-Turn** | One user prompt → one assistant response. `test_type` on the test set. |
| **Multi-Turn** | A conversation goal; Penelope drives multiple turns. `test_type` on the test set. |
| **`metric_scope`** | List on each metric: `["Single-Turn"]`, `["Multi-Turn"]`, or both. Platform **drops** metrics whose scope does not include the test's type. |
| **`score_type`** | `numeric` or `categorical` on a metric — how the evaluator returns a score. Not the same as `metric_scope`. |

---

## Workflow terms

| Term | Definition |
|---|---|
| **Discovery** | Explore an endpoint (`explore_endpoint`) to learn domain, capabilities, boundaries. |
| **Plan** | Structured proposal: behaviors, metrics, test sets, mappings — **before** any create call. |
| **Reuse** | Use an existing behavior/metric (`list_*` + same name) instead of creating a duplicate. |
| **Generation prompt** | Text passed in `generate_test_set` `config` describing what the synthesizer should produce. |
| **Scope coverage** | Every behavior in a test set must have ≥1 linked metric whose `metric_scope` includes that set's `test_type`. |

---

## Common confusions

**Behavior vs metric** — Behavior = *what* should happen. Metric = *how* you measure it. Every behavior in a test set needs at least one linked metric before generation.

**Behavior vs category/topic** — Categories and topics are optional test-set labels for organization. They do not replace behaviors or metrics.

**Single-Turn test vs Single-Turn metric scope** — A Multi-Turn test set only runs metrics with `"Multi-Turn"` in `metric_scope`. Planning both explicitly avoids silent empty scores at run time.

**PRD section title vs behavior** — "Security" or "Operate Safely" is not a behavior. Split numbered requirements and acceptance criteria into testable expectations (see `prd-workflow.md`).

**Source vs pasted PRD** — Pasted text in chat is ephemeral. For large specs, `create_source` then pass the source id into `generate_test_set` (Single-Turn only).

---

## PRD traceability

| Term | Definition |
|---|---|
| **FR / AC** | Numbered functional requirement or acceptance criterion in a spec — primary source for **metrics**, not behavior titles. |
| **Assumption** | Something underspecified in the PRD that you infer; must be listed in the plan for user confirmation. |
| **TBD** | Requirement too vague to score — flag in plan; do not invent a numeric rubric. |

# PRD → test foundation workflow

Turn a **PRD, product spec, or requirements doc** into a durable **test foundation** on Rhesis: fine-grained behaviors, custom metrics, tags, behavior→metric links, and generated test sets.

**When to use this workflow** (not endpoint exploration):

- User chose **menu option 3** or pasted/attached a PRD, spec, guardrails doc, or requirements
- User asks to scaffold behaviors, build evaluation from requirements, or set up a test foundation
- User is onboarding an agent and has requirements but no test suite yet

**Skip** when the user only wants to explore an endpoint, run existing tests, or analyze results — use the platform workflow in `SKILL.md`.

**Write gate:** Present the full plan and get explicit approval before any `create_*` or `generate_*` call. PRD scaffolding creates org assets — never auto-create.

## Reference docs

| File | Purpose |
|---|---|
| [prd-anatomy.md](prd/prd-anatomy.md) | How real PRDs are structured |
| [behavior-design.md](prd/behavior-design.md) | Split bundled PRD text into behaviors |
| [metric-design.md](prd/metric-design.md) | AC-driven metrics (binary, categorical, numeric) |
| [scope-alignment.md](prd/scope-alignment.md) | `metric_scope` ↔ test set `test_type` (platform enforces at run time) |
| [metric-scope.md](../metric-scope.md) | When to use Single-Turn vs Multi-Turn (all workflows) |

## Pipeline

```
PRD intake → Extract behaviors → Design metrics (AC + scope) → Plan tags & test sets
→ User approval → Create → assign_tag → generate_test_set → Verify → Offer execution
```

## 1. PRD intake

Accept markdown, Confluence/Notion export, file attachment, or repo files. Expect mixed structure — see [prd-anatomy.md](prd/prd-anatomy.md).

Read for: stakeholder/legal blocks, persona stories, numbered FRs with `(P#)`, acceptance criteria quantifiers, appendices, TBD items.

If guardrails are vague, ask **one** focused question — otherwise infer defaults and note them in the plan.

## 2. Extract fine-grained behaviors

See [behavior-design.md](prd/behavior-design.md). One behavior = one testable expectation. Never use section titles, persona names, or umbrella labels ("Reliability", "Operate Safely") as behaviors.

Target **6–12 behaviors** for a typical agent PRD.

## 3. Design custom metrics

See [metric-design.md](prd/metric-design.md). Metrics come from **acceptance criteria / FR text**, not behavior names.

Every metric needs:

- `score_type`: `categorical` or `numeric` derived from AC language
- `metric_scope`: `["Single-Turn"]`, `["Multi-Turn"]`, or both — see [scope-alignment.md](prd/scope-alignment.md)
- `evaluation_prompt` quoting the source FR/AC with checkable bullets

Use `create_metric` during plan execution (not `generate_metric`).

## 4. Plan tags

`list_tags` once; reuse existing names. Assign 1–3 tags per behavior (`functional`, `safety`, `compliance`, `domain`, `quality`, `transparency`). Apply same tags to linked metrics when relevant.

## 5. Plan test sets

Split by **theme and `metric_scope`**. Each test set has one `test_type`. Every behavior in the set must have ≥1 linked metric whose `metric_scope` includes that type — run the coverage check in [scope-alignment.md](prd/scope-alignment.md) before approval.

- **Single-Turn** — guardrails, refusals, one-shot lookups
- **Multi-Turn** — context retention, multi-step threads from user stories

## 6. Present plan

Include: PRD summary, behaviors table, metrics table (with AC source + `metric_scope`), mappings, test sets table (with `test_type` and metrics expected to run), **scope coverage matrix** (see [metric-scope.md](metric-scope.md)).

End with: "Does this look right? Shall I create this test foundation on Rhesis?"

## 7. Create

Follow the **Creation phase** in `SKILL.md`, plus:

- Every new metric: set `metric_scope` from the plan
- After metrics exist, before `generate_test_set`: `assign_tag` for each planned tag (`entity_type`: `"Behavior"` or `"Metric"`)

## 8. Verify and hand off

Count-check entities, spot-check generated tests, summarize with links. Offer to **execute** test sets via the platform workflow once the endpoint is registered.

## PRD extraction checklist

- [ ] No umbrella behavior names or section titles as behaviors
- [ ] Every metric has explicit `metric_scope` and AC traceability
- [ ] Every test set passes scope coverage check (behaviors ↔ metrics ↔ `test_type`)
- [ ] Guardrail test sets include adversarial generation prompts
- [ ] Underspecified PRD items flagged — not invented rubrics

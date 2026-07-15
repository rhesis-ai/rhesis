# Requirements → test foundation

Turn a Product Requirements Document (PRD), product spec, or guardrails doc into behaviors, metrics, tags, mappings, and test sets on Rhesis.

**Read:** `use-case-bracketfeld.md` for the full deliverable shape. **Read:** `metric-scope.md` before presenting any plan.

---

## When to use

- User pasted or attached a PRD, product spec, or guardrails doc
- User chose menu option **Requirements → test foundation**
- User asks to scaffold behaviors/metrics from requirements

**Skip** `explore_endpoint` unless the user asks after the foundation exists.

**Write gate:** Present the full plan and get explicit approval before any `create_*` or `generate_*` call.

---

## Pipeline

```text
Intake → Extract behaviors → Design metrics from AC (+ metric_scope) → Plan tags & test sets
→ Scope matrix → Assumptions & gaps → User approval → Create → assign_tag → generate_test_set → Verify
```

---

## 1. Intake

Accept markdown, exports, or attachments. Read for: stakeholders, persona stories, numbered FRs with priorities, acceptance criteria, appendices, TBD items.

If guardrails are vague, ask **one** focused question — otherwise note assumptions in the plan.

Large specs: offer `create_source` (title + content) for Single-Turn grounding.

---

## 2. Behaviors

One behavior = one testable expectation. **Never** use section titles or persona names as behaviors.

Target **6–12 behaviors** for a typical agent requirements doc. Split bundled prose using the patterns in `use-case-bracketfeld.md` § Behavior extraction.

---

## 3. Metrics

Metrics come from **acceptance criteria / FR text**, not behavior titles.

Each metric needs: `score_type`, **`metric_scope`**, `evaluation_prompt` quoting the source FR/AC.

Use `create_metric` during execution (not `generate_metric`).

---

## 4. Test sets

Split by theme and **`metric_scope`**. One `test_type` per set. Run scope coverage check (`metric-scope.md`) before approval.

---

## 5. Present plan (required sections)

1. Requirements summary (2–3 sentences)
2. Behaviors table (reuse/new)
3. Metrics table (AC source, scope, score type, pass rule)
4. Mappings table
5. Test sets table (`test_type`, behaviors, generation_prompt summary)
6. **Scope coverage matrix**
7. Tags (if any)
8. **Assumptions & gaps** / TBD items
9. Approval question

---

## 6. Create

Follow `phases/creation.md`. Set `metric_scope` on every new metric. `assign_tag` after metrics, before `generate_test_set`.

---

## Checklist before approval

- [ ] No umbrella behavior names
- [ ] Every metric has AC traceability and `metric_scope`
- [ ] Scope matrix: all rows OK
- [ ] TBD items flagged, not invented rubrics
- [ ] Guardrail sets include adversarial generation prompts

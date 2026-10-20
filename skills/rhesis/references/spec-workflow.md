# Spec → test foundation

Turn a Product Requirements Document (PRD), product spec, or guardrails doc into requirements, metrics, tags, mappings, and test sets on Rhesis.

**Read:** `use-case-bracketfeld.md` for the full deliverable shape. **Read:** `metric-scope.md` before presenting any plan.

---

## When to use

- User pasted or attached a PRD, product spec, or guardrails doc
- User chose menu option **Spec → test foundation**
- User asks to scaffold requirements/metrics from a spec

**Skip** `explore_endpoint` unless the user asks after the foundation exists.

**Write gate:** Present the full plan and get explicit approval before any `create_*` or `generate_*` call.

---

## Pipeline

```text
Intake → Extract requirements → Design metrics from AC (+ metric_scope) → Plan tags & test sets
→ Scope matrix → Assumptions & gaps → User approval → Create → assign_tag → generate_test_set → Verify
```

---

## 1. Intake

Accept markdown, exports, or attachments. Read for: stakeholders, persona stories, numbered FRs with priorities, acceptance criteria, appendices, TBD items.

If guardrails are vague, ask **one** focused question — otherwise note assumptions in the plan.

Large specs: offer `create_source` (title + content) for Single-Turn grounding.

---

## 2. Requirements

One requirement = one testable expectation. **Never** use section titles or persona names as requirements.

**When the spec gives its requirements IDs** (R1, FR-2.1, REQ-3), use them as they are: one requirement per ID, named `<ID>: <requirement as written>`, with the acceptance criteria as the description. Don't reword, merge, split or re-number them. If the user asks for a subset ("R1-R3"), plan exactly that subset.

**When the spec is prose without IDs**, target **6–12 requirements** for a typical agent spec, keeping the spec's own wording. Split bundled prose using the patterns in `use-case-bracketfeld.md` § Requirement extraction.

---

## 3. Metrics

Metrics come from **acceptance criteria / FR text**, not requirement titles.

Each metric needs: `score_type`, **`metric_scope`**, `evaluation_prompt` quoting the source FR/AC.

Use `create_metric` during execution (not `generate_metric`).

---

## 4. Test sets

Split by theme and **`metric_scope`**. One `test_type` per set. Run scope coverage check (`metric-scope.md`) before approval.

The generator receives each requirement's name and description, so the acceptance criteria belong in the requirement. `generation_prompt` carries what the spec adds on top, quoted as written:

- its example scenarios and inputs ("Is this a migraine?")
- the exact triggers it lists, such as the red flags that must escalate
- the fixed replies or formats the agent must give
- behaviour across turns the criteria name ("no further history questions", "stays active in later turns")

Don't add scenarios, triggers or expectations the spec doesn't name.

---

## 5. Present plan (required sections)

1. Spec summary (2–3 sentences)
2. Requirements table (reuse/new)
3. Metrics table (AC source, scope, score type, pass rule)
4. Mappings table
5. Test sets table (`test_type`, requirements, generation_prompt summary)
6. **Scope coverage matrix**
7. Tags (if any)
8. **Assumptions & gaps** / TBD items
9. Approval question

---

## 6. Create

Follow `phases/creation.md`. Set `metric_scope` on every new metric. `assign_tag` after metrics, before `generate_test_set`.

---

## Checklist before approval

- [ ] No umbrella requirement names
- [ ] Every metric has AC traceability and `metric_scope`
- [ ] Scope matrix: all rows OK
- [ ] TBD items flagged, not invented rubrics
- [ ] Guardrail sets include adversarial generation prompts

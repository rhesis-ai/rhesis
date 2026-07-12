# Metric scope — matching metrics to tests

Every metric declares which test shapes it can evaluate via **`metric_scope`**. Every generated test has a **`test_type`** (`Single-Turn` or `Multi-Turn`). At run time the platform **keeps only metrics whose scope includes the test's type**. Mismatches are **silently dropped** — runs may complete with no metric scores.

**Rule:** Single-turn metrics evaluate single-turn tests; multi-turn metrics evaluate multi-turn tests. Plan both explicitly before creating anything.

---

## What each test type is

| `test_type` | Test shape | How it runs |
|---|---|---|
| **Single-Turn** | One `prompt` → one response | Direct call to the endpoint |
| **Multi-Turn** | A `goal` in test configuration | Penelope drives a conversation, then metrics score the transcript |

`generate_test_set` → `test_type` sets the shape for **every** test in that set. Use **separate test sets** when the PRD needs both one-shot probes and conversational flows.

---

## When to use `["Single-Turn"]`

Set `metric_scope: ["Single-Turn"]` when the pass/fail criterion is checkable from **one user message and one assistant reply**:

- Hard refusals — secrecy, fraud assistance, final-sale blocks
- One-shot format rules — "one-sentence denial", "≤ 30 days" stated in a single turn
- Off-topic redirect, policy gates, adversarial single prompts
- Factual accuracy or structure on a lone exchange

**Test set:** `test_type: "Single-Turn"` with behaviors and generation prompts that describe one-shot probes.

**Evaluation placeholders:** `{{prompt}}`, `{{response}}`, optional `{{expected_response}}`.

---

## When to use `["Multi-Turn"]`

Set `metric_scope: ["Multi-Turn"]` when the criterion needs a **full conversation** (`conversation_summary` / transcript):

- Context retention — "≥ 3 follow-ups without re-asking order ID"
- Multi-step threads — status lookup then refund eligibility in one session
- Goal achievement over several turns
- Session tone or escalation paths that only emerge across turns

**Test set:** `test_type: "Multi-Turn"` with `generation_prompt` describing the **thread goal**, not a single prompt.

**Evaluation:** rubric must reference transcript-level evidence, not a single reply in isolation.

---

## When to use `["Single-Turn", "Multi-Turn"]` (dual scope)

Use **sparingly** — only when the **same rubric** applies whether you have one reply or a full transcript (e.g. a coarse "stays within domain" check).

**Prefer splitting** when:

- Single-turn needs an adversarial one-liner; multi-turn needs a realistic user story
- The `evaluation_prompt` would differ between shapes

Dual scope is not a shortcut to avoid planning two test sets.

---

## Planning checklist

1. **`metric_scope` on every metric** — required on `create_metric`; include in save_plan / user-facing plan tables.
2. **`test_type` on every test set** — one type per set.
3. **Behaviors listed on each test set** — so coverage can be validated.
4. **Coverage rule** — for each test set *T* and behavior *B* in *T*:

   ∃ linked metric *M* such that `T.test_type ∈ M.metric_scope`

5. **Split when needed** — guardrails (Single-Turn) and retention (Multi-Turn) → two test sets, scoped metrics each.

### Plan tables (include scope columns)

**Metrics:**

| Metric | Behavior | `metric_scope` | Score type | Pass definition |

**Test sets:**

| Test set | `test_type` | Behaviors | Metrics expected to run |

**Coverage matrix (show user before approval):**

| Test set | test_type | Behavior | Linked metric | Scope OK? |

---

## PRD signals → scope (quick reference)

| PRD / AC signal | `metric_scope` | Test set `test_type` |
|---|---|---|
| "Shall not disclose…" (one probe) | `["Single-Turn"]` | Single-Turn |
| "Retain context ≥ N follow-ups" | `["Multi-Turn"]` | Multi-Turn |
| "One-sentence denial citing reason" | `["Single-Turn"]` | Single-Turn |
| Full user story thread (RS-04 style) | `["Multi-Turn"]` per retention FR | Multi-Turn |
| Same FR tested one-shot and in-thread | Two metrics or dual-scope (prefer two) | Matching sets |

See [prd/scope-alignment.md](prd/scope-alignment.md) for platform executor details and failure modes.

---

## Creation order

1. Behaviors
2. Metrics **with `metric_scope` from the plan**
3. `add_behavior_to_metric` for every mapping
4. `generate_test_set` per test set — `test_type` must match linked metrics' scope
5. Tags (PRD workflow)

---

## Common mistakes

| Mistake | What happens |
|---|---|
| Multi-Turn test set, all metrics `["Single-Turn"]` | Preflight may warn; run produces no metric scores |
| Retention metric scoped Single-Turn only | Never runs on the Multi-Turn set |
| Omitted `metric_scope` on `create_metric` | Metric excluded on every run |
| Mixed guardrail + retention in one test set | Half the metrics silently dropped — **split test sets** |

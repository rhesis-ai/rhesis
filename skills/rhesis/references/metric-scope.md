# Metric scope — matching metrics to tests

> **Docs:** https://docs.rhesis.ai/docs/metrics/metric-scope.md

Every metric declares **`metric_scope`**. Every test set declares **`test_type`**. At run time the platform keeps only metrics whose scope includes the test's type. Mismatches are **silently dropped**.

See `definitions.md` for term disambiguation.

---

## When to use `["Single-Turn"]`

One prompt → one reply. Use for refusals, one-shot format rules, factual checks, adversarial probes.

Pair with a **Single-Turn** test set.

---

## When to use `["Multi-Turn"]`

Full transcript required — context retention, multi-step threads, session goals.

Pair with a **Multi-Turn** test set; `generation_prompt` describes the **thread goal**.

---

## When to use both

Rare — same rubric for one reply or full transcript. Prefer two metrics + two test sets when probes differ.

---

## Planning checklist

1. `metric_scope` on every metric (copy from `list_metrics` when reusing).
2. One `test_type` per test set.
3. Behaviors listed on each test set.
4. Coverage: every behavior in a set has a linked metric whose scope includes that set's `test_type`.
5. Split guardrails (Single-Turn) and retention (Multi-Turn) into separate sets when needed.

---

## Plan tables (required before approval)

**Metrics:** Metric | Behavior | AC source | `metric_scope` | Score type | Pass definition

**Test sets:** Test set | `test_type` | Behaviors | Metrics expected to run

**Coverage matrix:** Test set | test_type | Behavior | Linked metric | Scope OK?

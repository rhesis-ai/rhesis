# Insights summary handoff

Use this when the user message is an **Insights handoff** (phrases like "summarize insights", "insights summary", "Insights page view").

## Intent

- Do **not** show the four-path menu.
- Do **not** start exploration or create entities.
- Re-fetch stats for the listed scope; do not trust pasted pass-rate numbers (there should be none).

## Scope from the prompt

Honor:

- Endpoint name
- Period / run selection
- Behavior names listed as in scope (client-side Insights filters)
- Test run IDs (already capped at ≤50)

If the prompt notes truncation (50 of N), mention that briefly in your reply.

## Tool sequence

1. Prefer `get_test_result_stats` with the provided `test_run_ids` (and/or the same date window Insights used). Start with overall aggregates, then by behavior / metric.
2. Identify weak behaviors and metrics.
3. Failures: `list_test_results` with Failed status + behavior scope; minimal `$select`. Call `get_test_result` only for a few samples.
4. Present: overall → by behavior → by metric → 2–3 failure examples → links to runs/tests.
5. Suggest concrete next steps (narrow filters, re-run weak behaviors, open failed cases).

## Nested run budget (inside ≤50 IDs)

| Runs in scope | Strategy |
|---|---|
| ≤ 10 | Aggregate stats + optional per-run `mode=all` on up to 3 weakest runs |
| 11–30 | Aggregate only; sample failures across scope (cap ~10 result details) |
| 31–50 | Aggregate + top 3 weakest behaviors; **no** per-run full-stats loop |

Never analyze more than the IDs listed in the handoff prompt.

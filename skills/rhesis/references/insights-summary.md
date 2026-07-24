# Insights summary handoff

Use this when the user message is an **Insights handoff** (phrases like "summarize insights", "insights summary", "Insights page view"). If the current message is **not** an Insights handoff (e.g. an ordinary "analyze my last run" request), ignore this section entirely and follow `result-analysis.md`.

## Intent

- Do **not** show the four-path menu.
- Do **not** start exploration or create entities.
- Re-fetch stats for the listed scope; do not trust pasted pass-rate numbers (there should be none).
- **Summarize across ALL the listed runs together — never pick a single run.** The handoff lists
  multiple test run IDs on purpose; the summary must aggregate every one of them.

## Scope from the prompt

Honor:

- Endpoint name
- Period / run selection
- Behavior names listed as in scope (client-side Insights filters)
- Test run IDs (already capped at ≤50) — treat these as one combined scope, not a list to choose from

If the prompt notes truncation (50 of N), mention that briefly in your reply.

## Tool sequence

Always pass the **full `test_run_ids` array** (every ID from the prompt) with an **explicit `mode`**.
Never rely on the default mode, and never call these with a single `test_run_id` — that would
summarize just one run.

1. Get the pooled stats across all runs in one call:

   ```
   get_test_result_stats
     mode=all
     test_run_ids=[<every ID from the prompt>]
   ```

   With `mode=all` this returns overall totals, per-behavior and per-metric pass rates pooled across
   the whole scope, plus a per-run table — all aggregated over every listed run. If you only need a
   single dimension, use `mode=summary`, `mode=behavior`, or `mode=metrics`, each still with the full
   `test_run_ids` array.
2. Identify the weak behaviors and metrics from the pooled numbers.
3. Failures: `list_test_results` with Failed status + behavior scope across the same `test_run_ids`;
   minimal `$select`. Call `get_test_result` only for a few samples.
4. Present: overall (across all runs) → by behavior → by metric → 2–3 failure examples → links to
   runs/tests.
5. Suggest concrete next steps (narrow filters, re-run weak behaviors, open failed cases).

Do **not** follow the per-run behavior-breakdown loop from `result-analysis.md` for an Insights
handoff — that loop (one `test_run_id` per call) is for comparing two runs. Pass all IDs at once so
the stats pool across the whole scope. `mode=test_runs` (per-run rows) is optional and only for an
at-a-glance per-run table **after** the pooled summary — never a substitute for the aggregate.

## Nested run budget (inside ≤50 IDs)

The pooled aggregate (step 1, all IDs) is always done first. This budget only limits the *optional*
per-run drill-down that follows it:

| Runs in scope | Strategy |
|---|---|
| ≤ 10 | Aggregate across all runs + optional per-run `mode=all` on up to 3 weakest runs |
| 11–30 | Aggregate across all runs only; sample failures across scope (cap ~10 result details) |
| 31–50 | Aggregate across all runs + top 3 weakest behaviors; **no** per-run full-stats loop |

Never analyze more than the IDs listed in the handoff prompt.

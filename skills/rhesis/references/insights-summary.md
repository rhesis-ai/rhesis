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
- Requirement names listed as in scope (client-side Insights filters)
- Test run IDs (already capped at ≤50) — treat these as one combined scope, not a list to choose from

If the prompt notes truncation (50 of N), mention that briefly in your reply.

## Tool sequence

Always pass the **full `test_run_ids` array** (every ID from the prompt) with an **explicit `mode`**.
Never rely on the default mode, and never call these with a single `test_run_id` — that would
summarize just one run.

1. Get the pooled stats across all runs, passing every ID at once:

   ```
   get_insights
     entity=test_result
     group_by=[requirement]
     measures=[count,passed,failed,pass_rate]
     test_run_ids=[<every ID from the prompt>]
   ```

   Passing the whole array pools the numbers across the scope rather than reporting one run.
   Omit `group_by` for overall totals alone, and repeat with `entity=metric`,
   `group_by=[metric_name]` for per-metric pass rates.
2. Identify the weak requirements and metrics from the pooled numbers.
3. Failures: `list_test_results` with Failed status + requirement scope across the same `test_run_ids`;
   minimal `$select`. Call `get_test_result` only for a few samples.
4. Present using the shape in `phases/analysis.md` — same sections and same caps, with
   "overall" meaning pooled across every run in scope rather than a single run.

Do **not** follow the per-run requirement-breakdown loop from `result-analysis.md` for an Insights
handoff — that loop (one `test_run_id` per call) is for comparing two runs. Pass all IDs at once so
the stats pool across the whole scope. Grouping by `test_run` for per-run rows is optional and only
for an at-a-glance table **after** the pooled summary — never a substitute for the aggregate.

## Nested run budget (inside ≤50 IDs)

The pooled aggregate (step 1, all IDs) is always done first. This budget only limits the *optional*
per-run drill-down that follows it:

| Runs in scope | Strategy |
|---|---|
| ≤ 10 | Aggregate across all runs + optional per-run `mode=all` on up to 3 weakest runs |
| 11–30 | Aggregate across all runs only; sample failures across scope (cap ~10 result details) |
| 31–50 | Aggregate across all runs + top 3 weakest requirements; **no** per-run full-stats loop |

Never analyze more than the IDs listed in the handoff prompt.

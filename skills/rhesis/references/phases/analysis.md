# Analysis phase

**Preferred:** `get_test_result_stats` with `mode=all` and `test_run_id`.

**Counts:** `get_test_run` → `attributes.total_tests` — never count list rows.

**Failures:** `list_test_results` with `$filter=test_run_id eq '<id>'` and minimal `$select`.

Retrieval details: `result-analysis.md`.

## Presenting a run — the only shape

This section owns the output format. Do not add sections it does not list, and do
not restate a number in prose that already appears in a table.

1. **Overall — one line.** Total, pass count, pass rate, and the run link:
   `8/10 passed (80%) — [Safety Test Suite](/test-runs/<id>)`
2. **By requirement — one table row each.** Name, pass rate, nothing else. No
   verdict adjectives, no commentary per row.
3. **By metric — one table row each.** Same rule.
4. **Failures — at most 3, two lines each:** the prompt snippet, then the
   evaluator's `reason`. If more failed, close the list with
   `N more failures in this run` and stop.
5. **Next steps — at most 3 bullets, one line each.** Name the action, not the
   rationale. Skip this section entirely when everything passed.

The shape does **not** change with the pass rate. A run that mostly failed gets
the same compact structure as one that mostly passed — only the failure list
differs, and it is still capped at 3.

**When the `reason` does not explain the failure, open the trace.** A test that
errored, a response wrong in a way the prompt does not account for, or anything
the user asks "why was this slow" about: `list_traces(test_run_id=...)` then
`get_trace`. The span tree gives each LLM call, retrieval and tool invocation
with its own duration and status, so the failing or slow step names itself. Put
what you find in the failure's second line in place of the evaluator's `reason`,
not as an extra section.

**Human verdicts outrank the numbers above.** `list_annotations(test_run_id=...)`
is cheap; check it before writing step 4. A result a person marked Pass is not a
failure, so leave it out of the failure list and note it in one clause on the
overall line: `2 corrected by human annotation`. A result a person marked Fail
belongs in the list even when every metric passed, with their comment as the
`reason`. This is also why "everything passed" needs the check before you write
it: the metrics can all be green and a human still have failed the run.

## Comparison

`get_test_result_stats` with `mode=test_runs` and both `test_run_ids`.

1. **One line** with the pass rate delta: `72% → 85%, +13 points`.
2. **Regressed**, then **Improved** — one row per requirement or metric with its
   delta. Regressions first because they are what needs action.
3. **Unchanged** — a count, not a list.
4. Links to both runs.

Operational volume (how many runs, which test sets run most): `get_test_run_stats`.

## Insights handoff

When the user message is an Insights summarize handoff, follow `insights-summary.md`
for scope and tool sequence (no four-path menu; respect listed requirements and
≤50 run IDs). Presentation still follows this file.

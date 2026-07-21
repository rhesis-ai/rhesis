# Analysis phase

**Preferred:** `get_test_result_stats` with `mode=all` and `test_run_id`.

**Counts:** `get_test_run` → `attributes.total_tests` — never count list rows.

**Failures:** `list_test_results` with `$filter=test_run_id eq '<id>'` and minimal `$select`.

Present: overall pass rate → by behavior → by metric → 2–3 failure examples → link `[Run Name](/test-runs/<id>)`.

## Comparison

`get_test_result_stats` with `mode=test_runs` and both `test_run_ids`. Show pass rate delta, improved/regressed behaviors.

Operational volume: `get_test_run_stats`.

Details: `result-analysis.md`.

## Insights handoff

When the user message is an Insights summarize handoff, also follow `insights-summary.md` (no four-path menu; respect listed behaviors and ≤50 run IDs).

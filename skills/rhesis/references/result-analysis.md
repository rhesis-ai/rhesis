# Test Result Analysis

How to retrieve and interpret test run results after an `execute_test_set` call
completes.

This file covers **retrieval only**. The output format — sections, ordering, and
the caps on failures and next steps — lives in `phases/analysis.md`.

---

## Retrieving results

### Preferred: single call with `mode=all`

```
get_test_result_stats
  mode=all
  test_run_id="<uuid>"
```

Returns requirement pass rates, metric pass rates, overall totals, and timeline in one call. Use this immediately after execution for a complete post-run analysis. Most efficient option.

### Authoritative total counts

If you need the authoritative test count separately (e.g., for a progress message before stats are ready):

```
get_test_run(test_run_id="<uuid>")
```

The `attributes` field contains:
- `total_tests` — authoritative count of all tests in the run
- `execution_mode`
- `started_at`

Never count items from `list_test_results` for totals — the list may be paginated or truncated.

### Individual result details

```
list_test_results
  $filter=test_run_id eq '<uuid>'
  $select=id,status,prompt,requirement,metric_scores
```

Keep `$select` minimal. Add `response` only if you need the full endpoint response — it is a large field that causes truncation.

**Status values:** `Passed` | `Failed`

To understand a specific failure in depth, call `get_test_result` with the result ID. Key fields:
- `test_output.output` — the endpoint's actual response
- `test_metrics.metrics` — dict of metric name → `{is_successful, score, reason, threshold}`
- `reason` — the evaluator's explanation; most useful for failure analysis

---

## Run comparison

When the user asks to compare runs or detect regressions, use `get_test_result_stats`.

### High-level comparison (most common)

```
get_test_result_stats
  mode=test_runs
  test_run_ids=["<run-a-uuid>", "<run-b-uuid>"]
```

Returns per-run pass/fail counts and pass rates in a single call. Best starting point for "did anything change between these runs?"

### Requirement-level breakdown

Call separately for each run:

```
get_test_result_stats
  mode=requirement
  test_run_id="<run-a-uuid>"
```

```
get_test_result_stats
  mode=requirement
  test_run_id="<run-b-uuid>"
```

Compare the per-requirement pass rates to identify which requirements improved and which regressed.

### Metric-level breakdown

```
get_test_result_stats
  mode=metrics
  test_run_id="<uuid>"
```

Use when the user wants to understand which evaluation criteria changed between runs.

---

## Finding runs to compare

If the user hasn't specified which runs to compare:

```
list_test_runs
  $filter=status/name eq 'Completed'
  $select=id,name,status,created_at
```

Present the available options and ask the user which runs they want to compare.

Alternatively, filter by endpoint or test set if the user references a specific context:

```
list_test_runs
  $filter=status/name eq 'Completed'
  $select=id,test_set,created_at
```

---

## Operational analytics (run volume, not outcomes)

For questions like "how many runs this month?" or "which test sets are run most?", use `get_test_run_stats` instead of `get_test_result_stats`:

```
get_test_run_stats
  mode=summary
```

```
get_test_run_stats
  mode=test_sets
```

```
get_test_run_stats
  mode=timeline
  months=3
```

This returns run volume, status distribution, top test sets by frequency, and monthly trends — not pass/fail outcomes. Use `get_test_result_stats` for pass/fail analysis.

---

## Drilling into a specific failure

To understand why a specific test failed:

```
get_test_result(test_result_id="<uuid>")
```

Returns: full prompt, full response, expected response, metric scores with individual reasoning, and evaluation metadata. Too expensive to call for all results — use selectively on notable failures only.

---

## Insights handoff

When the message is an Insights page summarize handoff, follow `insights-summary.md`: skip the menu, re-fetch with the listed `test_run_ids` / requirements, enforce the nested ≤50-run budget, then present aggregates and a few failure samples.

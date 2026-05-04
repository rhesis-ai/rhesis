# Test Result Analysis

How to retrieve, interpret, and present test run results after an `execute_test_set` call completes.

---

## Retrieving results

### Preferred: single call with `mode=all`

```
get_test_result_stats
  mode=all
  test_run_id="<uuid>"
```

Returns behavior pass rates, metric pass rates, overall totals, and timeline in one call. Use this immediately after execution for a complete post-run analysis. Most efficient option.

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
  $select=id,status,prompt,behavior,metric_scores
```

Keep `$select` minimal. Add `response` only if you need the full endpoint response — it is a large field that causes truncation.

**Status values:** `Passed` | `Failed`

To understand a specific failure in depth, call `get_test_result` with the result ID. Key fields:
- `test_output.output` — the endpoint's actual response
- `test_metrics.metrics` — dict of metric name → `{is_successful, score, reason, threshold}`
- `reason` — the evaluator's explanation; most useful for failure analysis

---

## Presenting a single-run summary

Structure your summary as:

1. **Overall**: total tests, pass count, fail count, pass rate percentage
2. **Failures by behavior**: group failed results by the `behavior` field; count failures per behavior
3. **Notable patterns**: any behavior or metric with a high failure rate (e.g., "3 of 4 failures came from the Safety Compliance metric")
4. **Link**: `[Test Set Name](/test-runs/<uuid>)` — use the test set name as link text, never a raw UUID

Example structure:
```
Results: 8/10 passed (80%)

Failures:
- Refuses Harmful Requests: 2 failures
- Maintains Conversation Context: 1 failure

Pattern: Safety Compliance metric failed on all 2 boundary-test prompts.

Full results: [Safety Test Suite](/test-runs/abc123)
```

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

### Behavior-level breakdown

Call separately for each run:

```
get_test_result_stats
  mode=behavior
  test_run_id="<run-a-uuid>"
```

```
get_test_result_stats
  mode=behavior
  test_run_id="<run-b-uuid>"
```

Compare the per-behavior pass rates to identify which behaviors improved and which regressed.

### Metric-level breakdown

```
get_test_result_stats
  mode=metrics
  test_run_id="<uuid>"
```

Use when the user wants to understand which evaluation criteria changed between runs.

### Presenting a comparison

Structure comparisons as:
- **Overall**: pass rate change (e.g., "72% → 85%, +13 points")
- **Improved**: behaviors or metrics that went from failing to passing
- **Regressed**: behaviors or metrics that went from passing to failing
- **Unchanged**: brief count of stable results
- **Links**: to both test runs so the user can drill into details

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

## Offering next steps after analysis

After presenting results, proactively offer relevant follow-ups:
- If pass rate is low: "Would you like me to improve any of these metrics, or adjust the test set to focus on different behaviors?"
- If a prior run exists for the same test set: "Would you like me to compare this with the previous run?"
- If there are failures concentrated in one behavior: "This behavior might need a stricter or more specific metric — want me to improve it?"

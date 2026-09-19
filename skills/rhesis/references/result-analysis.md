# Test Result Analysis

How to retrieve and interpret test run results after an `execute_test_set` call
completes.

This file covers **retrieval only**. The output format — sections, ordering, and
the caps on failures and next steps — lives in `phases/analysis.md`.

---

## Retrieving results

### Preferred: `get_insights`, one call per breakdown

Overall totals, and the requirement breakdown, in one call:

```
get_insights
  entity=test_result
  group_by=[requirement]
  measures=[count,passed,failed,pass_rate]
  test_run_ids=["<uuid>"]
```

The metric breakdown is a second call, because metrics are their own entity — one row per (result, metric):

```
get_insights
  entity=metric
  group_by=[metric_name]
  measures=[count,passed,failed,pass_rate]
  test_run_ids=["<uuid>"]
```

Omit `group_by` entirely for a single overall row, which is the cheapest way to get a run's totals.

Two calls cover a full post-run analysis. Prefer them to fetching results and counting: a `list_test_results` page can be truncated, and these are computed server-side over the whole run.

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

When the user asks to compare runs or detect regressions, use `get_insights`.

### High-level comparison (most common)

```
get_insights
  entity=test_result
  group_by=[test_run,test_run_id]
  measures=[count,passed,failed,pass_rate]
  test_run_ids=["<run-a-uuid>", "<run-b-uuid>"]
```

Per-run pass/fail counts and pass rates in a single call. Best starting point for "did anything change between these runs?"

`test_run` comes back as the run's name, which is what you show the user; `test_run_id` is the UUID, which is what goes in a link URL. Group by both so you have each.

### Requirement-level breakdown

Both runs in one call — group by requirement *and* run, then compare the rows:

```
get_insights
  entity=test_result
  group_by=[requirement,test_run]
  measures=[count,passed,failed,pass_rate]
  test_run_ids=["<run-a-uuid>", "<run-b-uuid>"]
```

Requirements whose pass rate moved between the two runs are the regressions and improvements.

### Metric-level breakdown

```
get_insights
  entity=metric
  group_by=[metric_name]
  measures=[count,passed,failed,pass_rate]
  test_run_ids=["<uuid>"]
```

Use when the user wants to understand which evaluation criteria changed. This entity also carries `human_annotation_count`, `automated_passed` and `automated_failed`, which is how you see where people overrode the automation.

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

For questions like "how many runs this month?" or "which test sets are run most?", switch entity rather than tool — `entity=test_run` is one row per run, where `entity=test_result` is one row per test execution:

```
get_insights
  entity=test_run
  group_by=[status]
  measures=[count]
```

```
get_insights
  entity=test_run
  group_by=[test_set]
  measures=[count]
```

```
get_insights
  entity=test_run
  group_by=[month]
  measures=[count]
  months=3
```

`executor` is also available, for who runs tests. These answer run volume, status distribution and trends — **not** pass/fail outcomes. Comparing outcomes between runs is `entity=test_result` grouped by `test_run`, because a run's pass rate is computed from its results.

---

## Drilling into a specific failure

To understand why a specific test failed:

```
get_test_result(test_result_id="<uuid>")
```

Returns: full prompt, full response, expected response, metric scores with individual reasoning, and evaluation metadata. Too expensive to call for all results — use selectively on notable failures only.

The response also carries what people made of this result: `last_annotation` (the newest human verdict, or null), `matches_annotation` (false when the human disagreed with automation), and `annotation_summary` (one entry per annotated metric or turn). Read those before explaining a result, because a human may already have corrected it.

---

## Seeing what the application actually did

This is a drill-down, not a step in every analysis. Pass rates, requirement and metric breakdowns and run comparisons are all answered above without a trace, and opening one to produce them costs context and adds nothing.

Reach for a trace when the result cannot answer the question: the response is wrong in a way the prompt does not explain, the test errored, or someone asks why it was slow or what it cost. One trace at a time, on the result that raised the question — never a sweep across a run.

```
list_traces(test_run_id="<uuid>")
get_trace(trace_id="<32-char hex>", project_id="<uuid>")
```

The span tree shows each operation inside the request with its own duration and status. The span whose `status_code` is `"ERROR"`, or whose `duration_ms` dominates the total, is the finding.

**`get_trace` is the expensive call.** Every span carries its full attributes and events — up to 8000 characters of prompt and 8000 of completion per LLM span, 10000 each of conversation input and output on the root — and nothing truncates the response. Read `span_count` on the listing row first: it says what opening the trace will cost.

When you only need to know *which* operation was slow or failed, `list_traces(root_spans_only=false)` answers that on its own. Those rows carry each span's name, duration and status and none of the payload, so they stay small however large the trace is. Open `get_trace` when you need what a span actually carried, on one trace, not in a loop over a run's results.

Four things worth knowing before you read one:

- **`status_code` on a listing is the root span's.** A trace whose inner LLM call failed can still show `OK`. Pass `root_spans_only=false` with `status_code="ERROR"` to land on the span that actually failed.
- **`get_trace` needs `project_id` as well as `trace_id`,** and `trace_id` is the 32-char hex, not a UUID. Both come from the `list_traces` row. Never ask the user for them.
- **An empty list usually means no project scope,** not that the run produced no traces. Pass `project_id` and try again before reporting an absence.
- **Narrow before you list.** A `list_traces` row is compact apart from `conversation_input`, which runs to 10000 characters, so a wide page over a busy project is still a lot of text. Filter by run, endpoint, status or duration rather than paging.

For cost and latency rather than one request's shape, `get_trace_metrics(project_id=…, test_run_id=…)` gives totals, error rate and p50/p95/p99. It is the only tool that reports either.

Traces exist for production traffic too, not just test runs: `trace_source="operation"` is how you answer questions about live behaviour.

---

## Checking what people already flagged

Automated scores are not the last word. A person can fail a test every metric passed, and when the two disagree the human verdict is the one the platform reports.

Before diagnosing a run, look at whether it has already been diagnosed:

```
list_annotations(test_run_id="<uuid>")
```

This covers the run's test results and the traces it produced. Add `resolved=false` for open items only.

Two things this changes in an analysis:

- **On a multi-turn result, a judgement may be about one turn.** `annotation_summary` keys entries as `target_type:reference`, so `turn:Turn 2` is a verdict on that turn alone rather than the whole conversation. Read `test_output.conversation_summary` to see which turn that was before explaining it.
- **A "failure" may be a known false positive.** If an annotation on a result says Pass while the metrics said Fail, the metric is the problem, not the endpoint. Say so rather than reporting the raw failure.
- **A clean-looking run may not be clean.** A human can fail a result everything passed. Never conclude "no problems found" from metric scores alone without checking.

When a comment names a metric, that judgement is about that metric specifically (`target_type: "metric"`, with the name in `target_reference`), not about the whole result.

---

## Insights handoff

When the message is an Insights page summarize handoff, follow `insights-summary.md`: skip the menu, re-fetch with the listed `test_run_ids` / requirements, enforce the nested ≤50-run budget, then present aggregates and a few failure samples.

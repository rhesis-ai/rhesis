# Execution phase

Run tests only when the user explicitly asks.

- Use **`execute_test_set`** with `test_set_identifier` and `endpoint_id`
- Do NOT create test configurations or test runs manually
- One call per test set if multiple
- Poll `get_job_status` on returned `task_id`; then use `test_run_id` for results

After creation, offer: "Would you like me to run these against [endpoint name]?"

See `phases/analysis.md` for presenting results.

## Running later

When the user wants tests to run later or regularly ("every morning", "nightly", "before Friday's
release"), use **`schedule_test_set`** instead of `execute_test_set`.

- Confirm the timing in plain words and the time zone before creating it
- Prefer a preset-shaped cron (one time a day, on chosen weekdays, or monthly); runs can be at most
  once an hour
- After creating, tell the user the `repeats` text and the next run time from the response
- To check on a schedule, use `get_test_run_schedule`; analyze its runs like any other run

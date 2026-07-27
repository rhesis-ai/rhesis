# Execution phase

Run tests only when the user explicitly asks.

- Use **`execute_test_set`** with `test_set_identifier` and `endpoint_id`
- Do NOT create test configurations or test runs manually
- One call per test set if multiple
- Poll `get_job_status` on returned `task_id`; then use `test_run_id` for results

After creation, offer: "Would you like me to run these against [endpoint name]?"

See `phases/analysis.md` for presenting results.

# Creation phase

Execute the approved plan exactly — no extra entities.

## Order (mandatory)

1. Reuse lookup — resolve IDs via `list_*` + `$filter` if needed
2. `create_project` — only if planned
3. `create_behavior` — **(new)** only; name + description
4. Resolve all behavior IDs
5. Metrics — **(reuse)** skip; **(improve)** `improve_metric`; **(new)** `create_metric` with plan name, **`metric_scope`**, `score_type`, `evaluation_prompt`. Do NOT use `generate_metric`
6. `add_behavior_to_metric` — all mappings before generation
7. `assign_tag` — if planned (PRD path); `entity_type` `Behavior` or `Metric`
8. `generate_test_set` — per set; `config.behaviors`, `generation_prompt`, `test_type`, optional `sources` (Single-Turn only). Prefer over `create_test_set_bulk` unless importing verbatim user prompts.
9. **Wait for generation** — call `await_task` with the `task_id`(s) from the responses. Do NOT poll `get_job_status` manually; the system resumes when all tasks finish.
10. `get_test_set` + `list_test_set_tests` spot-check generated prompts
11. Summarize by name (never IDs); offer execution: "Would you like me to run these against [endpoint name]?"

**Critical:** test sets are generated LAST, only after every behavior, metric, and behavior→metric link is in place. Calling `generate_test_set` before that point is rejected with "Cannot generate test sets yet…". Wait until the "Plan progress" line shows N/N for behaviors, metrics, and mappings.

## Naming

Title Case, 2–5 words. No snake_case or `check_` prefixes.

## Field constraints

- `metric_type`: `"custom-prompt"`; `backend_type`: `"custom"`
- `score_type`: `"numeric"` or `"categorical"` only
- `metric_scope`: non-empty; entries `"Single-Turn"` and/or `"Multi-Turn"`
- `threshold_operator`: `=`, `<`, `>`, `<=`, `>=`, `!=`
- `test_type`: `"Single-Turn"` or `"Multi-Turn"`
- `priority`: integer, not string
- `config.behaviors`: non-empty list of behavior **names**

## Never send

`id`, `user_id`, `organization_id`, `created_at`, `updated_at`, `owner_id`, `assignee_id`, `status_id`, `model_id`, `backend_type_id`, `metric_type_id`

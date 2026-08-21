# Creation phase

Execute the approved plan exactly — no extra entities.

## Order (mandatory)

1. Reuse lookup — resolve IDs via `list_*` + `$filter` if needed
2. `create_project` — only when the user asked for a **new** project. The session already has one; never create a project to "hold" this work
3. `create_requirement` — **(new)** only; name + description
4. Resolve all requirement IDs
5. Metrics — **(reuse)** skip; **(improve)** `improve_metric`; **(new)** `create_metric` with plan name, **`metric_scope`**, `score_type`, `evaluation_prompt`, plus `description`, `evaluation_steps`, `reasoning`, `explanation` written to the depth in `metric-authoring.md`. Do NOT use `generate_metric`
6. `add_requirement_to_metric` — all mappings before generation
7. `assign_tag` — if planned (PRD path); `entity_type` `Requirement` or `Metric`
8. `generate_test_set` — per set; `config.requirements`, `generation_prompt`, `test_type`, optional `sources` (Single-Turn only). **Read `test_type` from the plan** for each test set and pass it explicitly — Multi-Turn sets MUST send `test_type: "Multi-Turn"`. Prefer over `create_test_set_bulk` unless importing verbatim user prompts.
9. **Wait for generation** — call `await_task` with the `task_id`(s) from the responses. Do NOT poll `get_job_status` manually; the system resumes when all tasks finish.
10. `get_test_set` + `list_test_set_tests` spot-check generated prompts
11. Summarize by name (never IDs); offer execution: "Would you like me to run these against [endpoint name]?"

**Critical:** test sets are generated LAST, only after every requirement, metric, and requirement→metric link is in place. Calling `generate_test_set` before that point is rejected with "Cannot generate test sets yet…". Wait until the "Plan progress" line shows N/N for requirements, metrics, and mappings.

## Multi-Turn test sets

Multi-Turn and Single-Turn test sets produce structurally different tests. Getting this wrong creates a test set that says "Multi-Turn" but contains Single-Turn tests.

- **`generate_test_set`**: pass `test_type: "Multi-Turn"`. The synthesizer generates goals and instructions instead of prompts. Omitting `test_type` or leaving the default produces Single-Turn tests regardless of the test set name.
- **`create_test_set_bulk`**: pass `test_set_type: "Multi-Turn"`. Each test in the `tests` array must use `test_configuration` (with `goal`, optional `instructions`, `restrictions`, `scenario`, `max_turns`) instead of `prompt`, and set `test_type: "Multi-Turn"` on each test object. The server types each test from its own content, so tests carrying a `prompt` land as Single-Turn even inside a Multi-Turn set. Do NOT send `prompt` and `test_configuration` on the same test.

## Naming

Title Case, 2–5 words. No snake_case or `check_` prefixes.

## Metric depth

Send the full metric, not the minimum the API accepts. `description`, `evaluation_steps`,
`reasoning`, and `explanation` go on every `create_metric` call, written out — one sentence each is
a threadbare metric, not a shortcut. `evaluation_steps` uses the `Step N:` / `---` format. See
`metric-authoring.md` for the field-by-field requirements, worked examples, and anti-patterns.

## Field constraints

- `metric_type`: `"custom-prompt"`; `backend_type`: `"custom"`
- `score_type`: `"numeric"` or `"categorical"` only
- `metric_scope`: non-empty; entries `"Single-Turn"` and/or `"Multi-Turn"`
- `evaluation_steps`: steps joined by a line containing only `---`, each prefixed `Step N:` on its
  own line — a plain `1. … 2. …` list stores as a single step
- `threshold_operator`: `=`, `<`, `>`, `<=`, `>=`, `!=`
- `test_type`: `"Single-Turn"` or `"Multi-Turn"`
- `priority`: integer, not string
- `config.requirements`: non-empty list of requirement **names**

## Never send

`id`, `user_id`, `organization_id`, `created_at`, `updated_at`, `owner_id`, `assignee_id`, `status_id`, `model_id`, `backend_type_id`, `metric_type_id`

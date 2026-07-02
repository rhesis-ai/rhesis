# Rhesis MCP Tool Catalog

All tools exposed by the Rhesis MCP server, grouped by workflow phase.

> This file is hand-maintained. When `mcp_tools.yaml` changes, update this file to match.
> A generator script (`build_skill.py`) that auto-derives this from the YAML is a planned v2 improvement.

---

## Discovery

### `list_endpoints`
List configured endpoints (the AI systems under test).

**Key parameters:** `$select`, `$filter`, `$top`, `$skip`

**Typical call:** `$select=name,id,url,description`

---

### `create_endpoint`
Register a new REST API endpoint (the AI system to be tested — a chat API, completion API, or chatbot).

Resolve the target project **first** with `list_projects` and pass its id — the endpoint cannot be created without a `project_id`. After creating, verify reachability with `check_endpoint`.

**Key parameters:**
- `name` (required) — endpoint name, unique within the project
- `project_id` (required) — UUID of the owning project; resolve via `list_projects`
- `connection_type` — `"REST"` for HTTP APIs (default for chatbots)
- `url` (required for REST) — full endpoint URL, e.g. `https://api.example.com/chat`
- `method` — HTTP method, e.g. `"POST"` or `"GET"`
- `description` — what the endpoint does
- `environment` — `"production"`, `"staging"`, `"development"`, or `"local"` (default `"development"`)
- `request_headers` — object of HTTP headers, e.g. `{"Content-Type": "application/json"}`
- `request_mapping` — object mapping the request body, using `{{ input }}` for the user message, e.g. `{"message": "{{ input }}"}`
- `response_mapping` — object mapping the response via JSONPath, e.g. `{"output": "$.response"}`
- `query_params` — optional object of query-string parameters
- `response_format` — `"json"` (default), `"xml"`, or `"text"`

**Auth (optional):**
- `auth_type` — `"bearer_token"`, `"client_credentials"`, or `"api_key"`; omit for unauthenticated endpoints
- `auth_token` — bearer token / API key (write-only, stored encrypted)
- `client_id`, `client_secret`, `token_url`, `scopes`, `audience` — OAuth client-credentials fields (`client_secret` is write-only, stored encrypted)

**Common mistakes:** Omitting `project_id` — the create fails because it is a required relationship. Always resolve the project with `list_projects` first. Do NOT send server-managed fields (`id`, `user_id`, `organization_id`, `status_id`, `created_at`, `updated_at`) — `status_id` is auto-assigned to "Active".

---

### `check_endpoint`
Send a test message to an endpoint to verify it is reachable and responding.

Use this before exploring or running tests — not when simply looking up endpoints.

**Key parameters:**
- `endpoint_id` (required) — UUID of the endpoint
- `input` — simple test message string, e.g. `"hello"`

---

### `explore_endpoint`
Run a multi-turn Penelope exploration of an endpoint to discover its domain, capabilities, limits, and response patterns. This is an **async operation** — the response includes a `task_id` to poll via `get_job_status`.

**Status flow:** PENDING → STARTED → PROGRESS → SUCCESS | FAILURE

When `SUCCESS`, the `result` field contains the full exploration findings:
- `findings` — structured findings from Penelope
- `strategy_findings` — strategy-formatted findings (when a named strategy was used)
- `conversation` — turn-by-turn conversation summary
- `goal_achieved`, `turns_used`, `status`
- `duration_ms`, `strategy`, `goal`, `endpoint_id`

**Key parameters:**
- `endpoint_id` (required, path parameter) — UUID of the endpoint
- `strategy` — `"domain_probing"`, `"capability_mapping"`, `"boundary_discovery"`, or `"comprehensive"`. Generates `goal` and `instructions` automatically.
- `goal` (required when no `strategy`) — what to learn about the endpoint
- `instructions` — optional probing instructions
- `scenario` — optional persona/context for Penelope
- `restrictions` — optional constraints to verify
- `previous_findings` — structured findings from a prior run; strategies build on them

**Common mistakes:** Calling this with a `strategy` AND a `goal` when you want the strategy to generate the goal automatically. Set only `strategy`, or set only `goal` (no strategy).

See `references/exploration-strategies.md` for strategy details.

---

## Core listing

### `list_projects`
List projects. Projects group related test sets and test runs.

**Key parameters:** `$select=name,id,description`, `$filter`, `$top`

---

### `list_test_sets`
List test sets in the organization. Test sets group related tests sharing a behavior, category, or theme.

**Key parameters:** `$select=name,id,description`, `$filter`

---

### `list_tests`
List individual tests. Each test defines a prompt and expected behavior.

**Default fields returned:** `id`, `prompt`, `behavior`, `category`, `topic`, `test_set`

---

### `list_behaviors`
List available behaviors. Behaviors define what an endpoint should do.

**Key parameters:** `$select=name,id,description`, `$filter=contains(tolower(name), 'safety')`

**Always call at the start of planning** with `$select=name,id,description` to avoid creating duplicates.

---

### `list_categories`
List available categories (e.g., "functional", "safety", "robustness").

**Key parameters:** `$select=name,id`

---

### `list_topics`
List available topics (e.g., "healthcare", "finance").

**Key parameters:** `$select=name,id`

---

### `list_metrics`
List evaluation metrics.

**Default fields returned:** `id`, `name`, `description`, `score_type`, `threshold`, `metric_scope` (excludes `evaluation_prompt` for efficiency)

**Always call at the start of planning** to find existing metrics before creating new ones.

---

### `list_test_runs`
List test runs. Each run tracks one execution of a test set.

**Key fields:** `id`, `status`, `test_set`, `endpoint`, `created_at`, `completed_at`

**Status values:** Queued → Running → Completed | Failed

**Typical call:** `$select=id,status,test_set,created_at`, `$filter=status/name eq 'Completed'`

---

### `list_test_results`
List test results. Each result contains the prompt sent, the response, status, and evaluation scores.

**Default fields returned:** `id`, `status`, `prompt`, `behavior`, `metric_scores` (excludes `response` by default)

**Always filter by run:** `$filter=test_run_id eq '<uuid>'`

**Common mistakes:** Including `response` in `$select` without a specific reason — this makes payloads large and risks truncation.

---

## Inspection

### `get_test_run`
Get details of a specific test run including status, timing, and the `attributes` field.

**Use this for accurate test counts** — `attributes` contains `total_tests`, pass counts, and `started_at`. Never count items from `list_test_results` for totals.

**Key parameters:** `test_run_id` (path parameter, required)

---

### `get_test_result`
Get full details of a specific test result. Use this to drill into individual failures and understand why a test failed.

**Key fields in the response:**
- `test_output.output` — the endpoint's actual response text
- `test_metrics.metrics` — dict of metric name → evaluation result, each containing:
  - `is_successful` — whether this metric passed
  - `score` — the numeric or categorical score
  - `reason` — the evaluator's explanation of why this score was given (most useful for failure analysis)
  - `threshold` — the pass/fail threshold (numeric metrics)
- `status` — overall pass/fail for this test result

Use the result IDs from `list_test_results` (filtered to failures) to identify which to drill into. Focus on the 2–3 most informative failures rather than fetching every one.

**Key parameters:** `test_result_id` (path parameter, required)

---

### `get_metric_behaviors`
List all behaviors currently linked to a metric.

Use to verify behavior associations before calling `add_behavior_to_metric`.

**Key parameters:** `metric_id` (path parameter, required)

---

### `get_job_status`
Poll the status of a background job started by `explore_endpoint`, `generate_test_set`, or `execute_test_set`.

**Status flow:** PENDING → STARTED → PROGRESS → SUCCESS | FAILURE

When `SUCCESS`, the `result` field contains job-specific data:
- `explore_endpoint` — full exploration findings (domain, capabilities, conversation, `strategy_findings`)
- `generate_test_set` — `test_set_id` (UUID of the created test set)
- `execute_test_set` — use the `test_run_id` returned in the original response

When `FAILURE`: the `error` field describes what went wrong.

**Key parameters:** `task_id` (path parameter, required)

---

## Entity mutation

### `create_project`
Create a new project.

**Key parameters:** `name` (required), `description`

**Common mistakes:** Creating a project when one isn't needed. Only propose this for large new test suites.

---

### `create_behavior`
Create a behavior with a name and description.

Call this **before** `create_test_set_bulk` so that when test objects reference the behavior by name, the server finds the pre-created behavior (with its description) rather than auto-creating a stub with no description.

**Key parameters:**
- `name` (required) — Title Case, e.g. `"Refuses Harmful Requests"`
- `description` (required) — explain what the behavior means and how it should be evaluated

---

### `update_behavior`
Update an existing behavior's fields.

Useful for adding a description to a behavior that was auto-created without one.

**Key parameters:**
- `behavior_id` (required, path parameter)
- `name` — optional, omit to keep unchanged
- `description`

---

### `create_metric`
Create a new evaluation metric with full control over all fields.

Prefer `generate_metric` when you know what to measure but don't want to fill every field manually. During plan execution, always use `create_metric` (not `generate_metric`) so the metric gets the exact name from the plan.

**Key parameters:**
- `name` (required) — Title Case, unique within the organization
- `metric_type` (required) — must be `"custom-prompt"` for user-defined metrics
- `backend_type` (required) — must be `"custom"`
- `score_type` (required) — must be exactly `"numeric"` or `"categorical"`
- `evaluation_prompt` (required) — the prompt template used to score responses; may use `{{prompt}}`, `{{response}}`, `{{expected_response}}`
- `metric_scope` (required) — list of strings, each must be `"Single-Turn"` or `"Multi-Turn"`
- For numeric metrics: `min_score`, `max_score`, `threshold`, `threshold_operator` (one of `"="`, `"<"`, `">"`, `"<="`, `">="`, `"!="`)
- For categorical metrics: `categories` (non-empty list), `passing_categories` (subset of `categories`)

**Never send:** `id`, `user_id`, `organization_id`, `created_at`, `updated_at`, `owner_id`, `status_id`, `model_id`, `backend_type_id`, `metric_type_id`

---

### `generate_metric`
Auto-generate a complete metric from a natural-language description.

An LLM produces all required fields and the metric is persisted automatically. Use this when you know what to measure but don't want to fill every field manually. Returns the created metric object.

**Do NOT use this during plan execution** — it produces its own metric name, which may differ from the plan.

**Key parameters:**
- `prompt` (required) — e.g., `"measure whether responses are factually accurate, on a 1-5 numeric scale"`

---

### `improve_metric`
Improve an existing metric with natural-language edit instructions.

The LLM reads the current metric fields and applies the requested changes. The metric is updated in place and returned.

**Key parameters:**
- `metric_id` (required, path parameter)
- `prompt` (required) — e.g., `"lower the threshold to 2"`, `"switch to categorical with pass/fail categories"`

---

### `add_behavior_to_metric`
Link a behavior to a metric so the metric is used to evaluate that behavior during test runs.

Both entities must already exist. Idempotent — calling it again for the same pair is a no-op.

**Key parameters:**
- `metric_id` (required, path parameter)
- `behavior_id` (required, path parameter)

---

## Test-set creation

### `generate_test_set` (preferred)
Generate a test set using the Rhesis synthesizer. An LLM creates diverse test prompts based on the generation config. Tests are persisted automatically. This is an async operation — the response includes a `task_id` to poll via `get_job_status`.

**Key parameters:**
- `name` (required) — test set name
- `config` (required object):
  - `generation_prompt` (required) — detailed description of what to test and how; be specific
  - `behaviors` (required, non-empty list of strings) — behavior names the tests target
  - `categories` (optional list of strings)
  - `topics` (optional list of strings)
- `num_tests` — integer, default 5, typical range 3–20
- `test_type` — `"Single-Turn"` (default) or `"Multi-Turn"`
- `sources` — optional list of knowledge source objects to ground tests in real content. Each object must contain only the `id` field: `[{"id": "<source-uuid>"}]`. The backend fetches and injects source content automatically — do NOT fetch or pass content yourself. Use `list_sources` to discover available sources. Only works with Single-Turn; ignored for Multi-Turn.

**Common mistakes:** Omitting `config.behaviors`, using `test_type: "single-turn"` (wrong case).

---

### `create_test_set_bulk`
Create a test set with manually specified tests.

Use this **only** when importing specific user-provided test prompts that must be used verbatim. For AI-generated content, prefer `generate_test_set`.

**Key parameters:**
- `name` (required)
- `description`
- `tests` (required, non-empty array) — each item: `{"prompt": {"content": "...", "language_code": "en"}, "behavior": "name", "category": "name", "topic": "name"}`
- `priority` — integer (1, 2, 3), not a string

---

## Knowledge sources

### `list_sources`
Discover available knowledge sources (documentation, FAQs, product specs, etc.) that can be used to ground test generation.

Use when the user mentions "based on our docs", "use the product spec", "I have reference material", or similar. Search by name with `$filter=contains(tolower(title), 'keyword')`.

**The agent must never fetch or pass source content directly.** Pass source IDs to `generate_test_set` and the backend handles content injection automatically.

**Default fields returned:** `id`, `title`, `description`, `url`, `source_type_id`, `status_id`

**Key parameters:** `$filter` (search by title), `$select`

---

## Execution

### `execute_test_set`
Run a test set against an endpoint. The backend creates the internal test configuration and queues the run automatically — you do not need to manage this.

The response includes `test_run_id` and `task_id`. Poll `get_job_status` with `task_id` until `SUCCESS`, then use `test_run_id` to fetch results via `get_test_run` and `list_test_results`.

**Key parameters:**
- `test_set_identifier` (required, path parameter) — test set UUID, nano_id, or slug
- `endpoint_id` (required, path parameter) — UUID of the target endpoint

---

## Analytics

### `get_test_result_stats`
Aggregated statistics for test results. Use for single-run analysis and multi-run comparison.

**Mode parameter:**
- `all` — complete stats for a single run: behavior pass rates, metric pass rates, overall totals, and timeline. **Use this with a single `test_run_id` immediately after execution — most efficient option for post-run analysis.**
- `behavior` — pass rates grouped by behavior; use with `test_run_id`
- `metrics` — pass rates grouped by metric name; use with `test_run_id`
- `test_runs` — per-run pass/fail summary; pass multiple `test_run_ids` to compare runs side by side
- `summary` — lightweight overall totals only

**For single-run analysis:** `mode=all` with `test_run_id`
**For multi-run comparison:** `mode=test_runs` with `test_run_ids`

**Key parameters:**
- `mode`
- `test_run_ids` — array of UUIDs for multi-run comparison
- `test_run_id` — single UUID
- `behavior_ids`, `test_set_ids` — optional filters
- `start_date`, `end_date` — ISO format

---

### `get_test_run_stats`
Run-level analytics: run volume, status distribution, most-run test sets, top executors, monthly trends.

Use for **operational questions** ("how many runs this month?"). For pass/fail outcomes, use `get_test_result_stats` instead.

**Modes:** `summary` (default), `status`, `results`, `test_sets`, `executors`, `timeline`, `all`

**Key parameters:**
- `mode`
- `endpoint_ids`, `test_set_ids` — optional filters
- `months` — history window (default 6)
- `start_date`, `end_date`

---

## Inspection (get-by-id)

### `get_test_set`
Get one test set by UUID, nano_id, or slug.

**CHAIN:** after `generate_test_set` / `get_job_status` → then `list_test_set_tests` to verify prompts.

**Key parameters:** `test_set_identifier` (required)

---

### `list_test_set_tests`
List tests inside a single test set.

**CHAIN:** prefer over org-wide `list_tests` when you have the test set ID.

**Default `$select`:** `id,prompt,behavior,category,topic`

**Key parameters:** `test_set_identifier` (required)

---

### `get_endpoint`
Full endpoint config including mappings and auth.

**CHAIN:** after `list_endpoints` when you need `request_mapping` / `response_mapping` details.

**Key parameters:** `endpoint_id` (required)

---

### `get_metric`
Full metric including `evaluation_prompt`.

**CHAIN:** before `update_metric` or `improve_metric`.

**Key parameters:** `metric_id` (required)

---

## Entity mutation (additional)

### `update_test_set`
Update test set metadata only (name, description). Does not regenerate tests.

**Key parameters:** `test_set_identifier` (required; UUID, nano_id, or slug); send only fields to change.

---

### `update_metric`
Direct field edits on a metric. Does not change behavior links.

**CHAIN:** `get_metric` first. For NL refactors use `improve_metric` instead.

**Key parameters:** `metric_id` (required)

---

### `remove_behavior_from_metric`
Unlink a behavior from a metric. Inverse of `add_behavior_to_metric`.

**CHAIN:** confirm link via `get_metric_behaviors` first.

**Key parameters:** `metric_id`, `behavior_id` (required)

---

### `create_source`
Create a knowledge source for grounding single-turn `generate_test_set`.

**Patterns:**
- Pasted text: `title` + `content` (Manual type — copy `source_type_id` from `list_sources`)
- URL: `title` + `url` (Website type)
- File uploads: UI only (not available via MCP)

**CHAIN:** `create_source` → `generate_test_set` with `sources: [{"id": "…"}]`

---



### `get_project`
Get one project by ID.

**CHAIN:** after `list_projects` when you need full project detail before `create_endpoint`.

**Key parameters:** `project_id` (required)

---

### `get_behavior`
Get one behavior including linked metrics.

**CHAIN:** complement `get_metric_behaviors` — behavior-centric view of metric links.

**Key parameters:** `behavior_id` (required)

---

### `get_test`
Get one test with full prompt and configuration.

**CHAIN:** after `list_test_set_tests`; before `update_test`.

**Key parameters:** `test_id` (required)

---

### `update_test`
Fix an individual test prompt without regenerating the whole set.

**CHAIN:** `get_test` first. Send only fields to change.

**Key parameters:** `test_id` (required)

---

### `get_test_set_metrics`
List metrics attached to a test set (execution overrides).

**CHAIN:** pre-flight before `execute_test_set`. Empty list → behavior metrics apply.

**Key parameters:** `test_set_identifier` (required)

---

### `get_test_set_last_run`
Most recent completed run for a test set + endpoint pair.

**CHAIN:** use for run comparison; pair with `get_test_result_stats(mode=test_runs)`.

**Key parameters:** `test_set_identifier`, `endpoint_id` (required)

---
## Playbooks

See `references/entity-model.md` for the full entity graph and tool chains by intent.

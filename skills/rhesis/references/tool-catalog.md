# Rhesis MCP Tool Catalog

All tools exposed by the Rhesis MCP server, grouped by workflow phase.

> This file is hand-maintained. When the MCP server's tool definitions change, update this file
> to match.

---

## Discovery

### `list_endpoints`
List configured endpoints (the AI systems under test).

**Key parameters:** `$select`, `$filter`, `$top`, `$skip`

**Typical call:** `$select=name,id,url,description`

---

### `create_endpoint`
Register a new REST API endpoint (the AI system to be tested — a chat API, completion API, or chatbot).

The endpoint is created in the current project automatically — do not resolve a project or ask which one to use. After creating, verify reachability with `check_endpoint`.

**Key parameters:**
- `name` (required) — endpoint name, unique within the project
- `project_id` — omit; the project scope is taken from the request
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

**Common mistakes:** Sending `project_id` — it is filled from the request scope, and passing one is how endpoints end up in the wrong project. Do NOT send server-managed fields (`id`, `user_id`, `organization_id`, `status_id`, `created_at`, `updated_at`) — `status_id` is auto-assigned to "Active".

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
List test sets in the organization. Test sets group related tests sharing a requirement, category, or theme.

**Key parameters:** `$select=name,id,description`, `$filter`

---

### `list_tests`
List individual tests. Each test defines a prompt and expected requirement.

**Default fields returned:** `id`, `prompt`, `requirement`, `category`, `topic`, `test_set`

---

### `list_requirements`
List available requirements. Requirements define what an endpoint should do.

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

**Default fields returned:** `id`, `status`, `prompt`, `requirement`, `metric_scores` (excludes `response` by default)

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

### `get_metric_requirements`
List all requirements currently linked to a metric.

Use to verify requirement associations before calling `add_requirement_to_metric`.

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

### `create_requirement`
Create a requirement with a name and description.

Call this **before** `create_test_set_bulk` so that when test objects reference the requirement by name, the server finds the pre-created requirement (with its description) rather than auto-creating a stub with no description.

**Key parameters:**
- `name` (required) — Title Case, e.g. `"Refuses Harmful Requests"`
- `description` (required) — explain what the requirement means and how it should be evaluated

**Common mistakes:** Requirement names are unique per organization, so creating one that already exists fails with "Requirement with this name already exists". Resolve it with `list_requirements` and reuse its id. Never retry with a suffixed name like `"Refuses Harmful Requests 2"`.

---

### `update_requirement`
Update an existing requirement's fields.

Useful for adding a description to a requirement that was auto-created without one.

**Key parameters:**
- `requirement_id` (required, path parameter)
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
- `evaluation_prompt` (required) — the evaluation criteria the judge applies. Criteria text only: placeholders like `{{response}}` are **not** substituted, and the engine already injects the input, response, context, and transcript
- `metric_scope` (required) — list of strings, each must be `"Single-Turn"` or `"Multi-Turn"`
- `description`, `evaluation_steps`, `reasoning`, `explanation` — optional to the API, expected in practice. Send all four, written out; see `metric-authoring.md` for the depth and for the `Step N:` / `---` format `evaluation_steps` must use

**Fields required by `score_type`.** These are enforced by the server but cannot be expressed in the JSON schema, so they are easy to miss:

| `score_type` | Also required |
|--------------|---------------|
| `"numeric"` | `min_score`, `max_score` **and** `threshold`. Optionally `threshold_operator` (one of `"="`, `"<"`, `">"`, `"<="`, `">="`, `"!="`, default `">="`) |
| `"categorical"` | `categories` (at least two labels) **and** `passing_categories` (at least one, each also present in `categories`) |

Send the numeric fields only for numeric metrics and the category fields only for categorical ones.

**Never send:** `id`, `user_id`, `organization_id`, `created_at`, `updated_at`, `owner_id`, `status_id`, `model_id`, `backend_type_id`, `metric_type_id`

**Common mistakes:** Sending `score_type: "numeric"` without `min_score`/`max_score`/`threshold` — rejected. Metric names are unique per organization, so creating one that already exists fails with "Metric with this name already exists"; resolve it with `list_metrics` and reuse it, or use `improve_metric`. Never retry with a suffixed name.

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

### `add_requirement_to_metric`
Link a requirement to a metric so the metric is used to evaluate that requirement during test runs.

Both entities must already exist. Idempotent — calling it again for the same pair is a no-op.

**Key parameters:**
- `metric_id` (required, path parameter)
- `requirement_id` (required, path parameter)

---

## Test-set creation

### `generate_test_set` (preferred)
Generate a test set using the Rhesis synthesizer. An LLM creates diverse test prompts based on the generation config. Tests are persisted automatically. This is an async operation — the response includes a `task_id` to poll via `get_job_status`.

**Key parameters:**
- `name` (required) — test set name
- `config` (required object):
  - `generation_prompt` (required) — detailed description of what to test and how; be specific
  - `requirements` (required, non-empty list of strings) — requirement names the tests target
  - `categories` (optional list of strings)
  - `topics` (optional list of strings)
- `num_tests` — integer, default 5, typical range 3–20
- `test_type` — `"Single-Turn"` (default) or `"Multi-Turn"`. Take this from the plan's test set and pass it explicitly. Omitting it produces Single-Turn tests no matter what the test set is called.
- `sources` — optional list of knowledge source objects to ground tests in real content. Each object must contain only the `id` field: `[{"id": "<source-uuid>"}]`. The backend fetches and injects source content automatically — do NOT fetch or pass content yourself. Use `list_sources` to discover available sources. Only works with Single-Turn; ignored for Multi-Turn.

`project_id` is resolved from the request scope — omit it.

**Common mistakes:** Omitting `config.requirements` (rejected with "At least one requirement must be specified"), omitting `name`, omitting `test_type` for a Multi-Turn test set. If this call fails, fix the argument it names and call it again — do **not** fall back to `create_test_set_bulk`, which stores only the prompts you write by hand and produces a far smaller test set than the user asked for.

**Verify afterwards:** generation can return tests attributed to requirements you did not pass. After `await_task`, run `list_test_set_tests` and confirm each test's `requirement` is one of the names in `config.requirements`. `Compliance`, `Reliability`, and `Robustness` are the seeded org defaults — seeing them when you asked for something else means the attribution is wrong, not that the tests are fine.

---

### `create_test_set_bulk`
Create a test set with manually specified tests.

Use this **only** when importing specific user-provided test prompts that must be used verbatim. For AI-generated content, prefer `generate_test_set`.

**Key parameters:**
- `name` (required)
- `description`
- `test_set_type` (required) — `"Single-Turn"` or `"Multi-Turn"`
- `tests` (required, non-empty array) — item shape depends on the test type:
  - Single-Turn: `{"prompt": {"content": "...", "language_code": "en"}, "requirement": "name", "category": "name", "topic": "name"}`
  - Multi-Turn: `{"test_type": "Multi-Turn", "test_configuration": {"goal": "...", "instructions": "...", "restrictions": "...", "scenario": "...", "max_turns": 10}, "requirement": "name", "category": "name", "topic": "name"}`
- `priority` — integer (1, 2, 3), not a string

Only `goal` is required inside `test_configuration`. A test uses either `prompt` or `test_configuration`, never both.

**Common mistakes:** Setting `test_set_type: "Multi-Turn"` but sending tests with `prompt` — the server types each test from its own content, so those tests land as Single-Turn inside a Multi-Turn set. Set `test_type` on every test object.

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
- `all` — complete stats for a single run: requirement pass rates, metric pass rates, overall totals, and timeline. **Use this with a single `test_run_id` immediately after execution — most efficient option for post-run analysis.**
- `requirement` — pass rates grouped by requirement; use with `test_run_id`
- `metrics` — pass rates grouped by metric name; use with `test_run_id`
- `test_runs` — per-run pass/fail summary; pass multiple `test_run_ids` to compare runs side by side
- `summary` — lightweight overall totals only

**For single-run analysis:** `mode=all` with `test_run_id`
**For multi-run comparison:** `mode=test_runs` with `test_run_ids`

**Key parameters:**
- `mode`
- `test_run_ids` — array of UUIDs for multi-run comparison
- `test_run_id` — single UUID
- `requirement_ids`, `test_set_ids` — optional filters
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

### `list_annotations`
List human annotations — judgements a person left on a test result, a trace or a test. Each carries a verdict in `status.name`, a free-text comment, the author, and a `resolved` flag.

The verdict is `Pass`/`Fail` on a test result, a trace, or an explorer test labelled by hand. It is `Accepted`/`Rejected` on a metric's own tuning case, where the person is judging what the *metric* said rather than what the system under test said.

Human annotations are ground truth: when an annotation disagrees with an automated metric score, **the annotation wins**. Use this to answer "what did people flag?", to explain why a test is considered wrong when metrics say it passed, and to find work still open.

An annotation names what it judges through `target_type`: the entity as a whole (`test_result`, `trace`, `test`), one `metric` by name, or one `turn` of a conversation. `target_reference` holds that name.

**Key parameters:**
- `test_run_id` — everything annotated in that run, both test results and the traces it produced. Main entry point.
- `test_set_id` — scope to annotations whose parent ran under a test configuration tied to that test set
- `endpoint_id` — scope to annotations whose parent ran against that endpoint
- `metric` — metric name or UUID (name is case-insensitive); returns every judgement about that metric. Two kinds are filed differently: one on a metric within a result names the metric, while a tuning judgement names the metric's id. Either input returns both, so this answers "what do people think of this metric" in one call
- `annotator_id` — UUID of a user; returns only annotations created by that person
- `requirement_id` — UUID of a requirement; scopes to annotations on test results linked to it
- `date_from` — ISO date (e.g. `"2026-01-15"`); annotations updated on or after this date
- `date_to` — ISO date (e.g. `"2026-01-31"`); annotations updated on or before this date
- `entity_type` — restrict to `"TestResult"`, `"Trace"` or `"Test"` (`Test` covers explorer labels and metric tuning judgements)
- `target_type` — restrict to `test_result`, `trace`, `test`, `metric` or `turn`
- `rating` — `"Pass"` or `"Fail"`, the human's verdict; tuning-case judgements use `"Accepted"` or `"Rejected"`
- `resolved` — pass `false` for open items only
- `search` — free text over comments, author, target reference and requirement name

**Linking:** use `context.trace_db_id` (a UUID) in a trace URL, never `context.trace_id` (32-char hex). Only the UUID resolves to a page. A tuning-case annotation carries `context.metric_id`, which is how you reach it — its `target_reference` is that same metric id, not a metric name.

---

### `get_annotation`
Get one annotation by UUID with its full comment, author, verdict and resolved state.

**CHAIN:** after `create_annotation` or `update_annotation` to re-read a row you just wrote.

**Key parameters:** `annotation_id` (required)

---

### `list_statuses`
List the organization's status rows, optionally for one entity type.

Statuses carry verdicts, which is why this matters: `create_annotation` takes a `status_id`, and which row you pass is the verdict you record. Pass and Fail live under `entity_type="TestResult"` and are what a judgement on a test result or a trace uses. Accepted and Rejected live under `"Annotation"` and belong to metric tuning.

Omitting `entity_type` returns several rows sharing a name across different entity types, so filter when you want a specific verdict.

**CHAIN:** before `create_annotation` / `update_annotation`.

**Key parameters:** `entity_type`

---

### `create_annotation`
Record a human verdict on a test result, a trace or a test. **Requires confirmation.**

**This records a judgement attributed to the person you are working for.** Only create one when they have told you what they concluded. Do not annotate to capture your own analysis of a result — say it in your answer instead.

A Pass/Fail annotation on a test result or trace **overrides that parent's automated status**, and the platform reports the corrected outcome from then on. It is a write against the parent as much as against the annotation.

**Key parameters:**
- `entity_type` (required) — `"TestResult"`, `"Trace"` or `"Test"`
- `entity_id` (required) — UUID of that entity
- `status_id` (required) — the Pass or Fail status UUID, from `list_statuses(entity_type="TestResult")`. Never guess it.
- `comments` — the person's reasoning in their words. An annotation with no comment explains nothing later.
- `target` — optional `{"type": "metric", "reference": "Answer Fluency"}` or `{"type": "turn", "reference": "Turn 2"}`. Omit for a verdict on the whole entity.

**Turn targets:** only meaningful on a multi-turn result or trace. Take the number from `test_output.conversation_summary` on `get_test_result`, where each turn carries its own, and write it exactly as `"Turn 2"`. The platform groups judgements by this reference, so `"2"` reads as a different target and would sit beside the turn's other annotations rather than superseding them.

**CHAIN:** `list_statuses(entity_type="TestResult")` → `create_annotation`.

**Careful:** `target` is nested on writes but flat (`target_type` / `target_reference`) on reads. Copying the flat pair from a `list_annotations` row into a create call is accepted and ignored, landing the annotation on the whole entity instead of the metric it named.

---

### `update_annotation`
Change an annotation's verdict, comment, target or resolved state. **Requires confirmation.**

Only the annotation's author may edit it; not even an admin can edit someone else's. Changing the verdict or target re-applies the override, so the parent's reported outcome moves with it.

**Key parameters:**
- `annotation_id` (required)
- `resolved` — `true` to resolve once the underlying problem is fixed, `false` to reopen. Resolving does not withdraw the verdict.
- `status_id`, `comments`, `target` — as for `create_annotation`

---

## Traces

A trace is one request's worth of work inside the application under test, and its spans are the individual operations: the LLM calls, retrievals and tool invocations, each with its own duration, status and model. A test result says what came back and what the metrics made of it. A trace says *why* it was that, which step was slow, and which one failed.

**These are diagnostic tools, not part of routine analysis.** Pass rates, requirement and metric breakdowns, and run comparisons are all answered by `get_insights` and `get_test_result` without a trace. Open one to answer a question the result cannot — an unexplained response, an errored test, a question about latency or cost — on the one result that raised it, never as a sweep across a run.

**A trace has two ids and they are not interchangeable.**

| Id | Shape | What it addresses |
|----|-------|-------------------|
| `trace_id` | 32-char hex | `get_trace` only |
| span row id | UUID | annotating a trace, a `/traces/…` link, `lookup_span` |

`list_traces` carries only the hex. The row id comes from `get_trace` as `root_spans[0].id`, or from a `list_annotations` row as `context.trace_db_id`. Using the hex where a row id belongs fails: there is no row with that id.

---

### `list_traces`
List traces, one row per trace by default (the root span).

Returns per row, newest first: `trace_id`, `project_id`, `start_time`, `duration_ms`, `span_count`, `root_operation`, `status_code`, `has_errors`, `environment`, `conversation_id`, `trace_metrics_status`, `conversation_input` (the request that started it — how you tell traces apart without opening them), the token and cost totals (`total_tokens` and `total_cost_usd`, each also split input/output, plus `total_cost_eur`), `models`, `providers`, the run links (`test_run_id`, `test_result_id`, `test_id`, `endpoint_id`, `endpoint_name`), and the human verdict where there is one (`has_annotations`, `verdict`, `last_annotation`, `matches_annotation`).

**Key parameters:**
- `test_run_id` — the traces one run produced, one per test execution. The usual entry point.
- `test_result_id` / `test_id` / `endpoint_id` / `conversation_id` — narrower provenance
- `status_code` — `"ERROR"` or `"OK"`. On the default view this is the **root** span's status, so a trace whose inner LLM call failed but whose root returned OK will not match. Pair with `root_spans_only=false`.
- `root_spans_only` — `false` returns every span as its own row, which is how you find the operation that actually failed
- `duration_min_ms` / `duration_max_ms` — how you answer "what was slow"; pair with `sort_by=duration_ms`
- `start_time_after` / `start_time_before` — ISO 8601
- `span_name` — exact operation name, e.g. `"ai.llm.invoke"`. Tests the row, so with the default `root_spans_only` it matches root spans only
- `search` — free text over trace id, operation names, **error messages**, endpoint name and URL, and conversation input/output. Searching an error message groups traces that failed the same way. It matches **any span** and returns the whole trace, so it finds a trace whose *inner* span carried the text even in the default view
- `trace_metrics_status` — `"Pass"`, `"Fail"`, `"Error"`, `"Inconclusive"` (only evaluated traces have one)
- `trace_source` — `"test"`, `"operation"` (production traffic) or `"all"`
- `trace_type` — `"Single-Turn"`, `"Multi-Turn"` or `"all"`
- `provider` — repeatable; a trace whose costs are not priced yet matches none, so this can hide recent traces
- `project_id` — omit to use the caller's scope
- `sort_by`, `sort_order`, `offset`

**Careful:** passing `search` makes `span_name` silently ignored — the route treats them as alternatives, not as an AND. Use one.

**Pagination:** the response carries `total`, `limit` and `offset`. Page with **`offset`** — this route does not take `skip`.

**Scoping:** with no project scope and no `project_id`, this returns only traces belonging to no project, which reads as an unexpectedly empty list. Pass `project_id` rather than reporting that there are no traces.

**CHAIN:** `get_test_run` or `get_insights` shows a failure → `list_traces` with that `test_run_id` → `get_trace` on the one that looks wrong.

---

### `list_trace_providers`
List the LLM providers appearing in this scope's traces.

These are the values `list_traces` accepts for `provider`, built from the same data that filter matches on. Get a name from here rather than guessing one: an unmatched provider returns an empty page rather than an error, which reads as "nothing used that provider" instead of as a typo.

A provider that neither the trace nor its model name identifies is reported as `"unknown"`. That is a real value to filter on, not a gap — those traces exist, and filtering to them is how you find what is unattributed.

**Key parameters:** `project_id` (omit to use the caller's scope)

**CHAIN:** `list_trace_providers` → `list_traces` with `provider`, the way `list_statuses` comes before `create_annotation`.

---

### `get_trace`
Get one trace with its full span tree: every operation nested parent to child, each with duration, status, model, cost and attributes.

The span whose `status_code` is `"ERROR"`, or whose `duration_ms` dominates the total, is the answer to "why".

**This response can be very large, and nothing truncates it.** Every span carries its full `attributes`, `events` and `trace_metrics` — up to 8000 characters of prompt and 8000 of completion on an LLM span, and up to 10000 each of conversation input and output on the root. A twenty-span trace runs to tens of thousands of tokens.

`span_count` on the `list_traces` row tells you the size before you pay for it. When it is large, or when you only need which operation was slow or failed, use `list_traces(root_spans_only=false)` — compact rows with name, duration and status, no attributes. Open `get_trace` when you need what a span actually carried, one trace at a time, never in a loop.

**Key parameters:**
- `trace_id` (required) — the 32-char hex, from a `list_traces` row or `context.trace_id`
- `project_id` (**required**) — unusual for this API, where scope is normally implicit. Take it from the `list_traces` row or `context.project_id`; never ask the user for it.

**The row id lives here.** `root_spans[0].id` is what annotates the trace as a whole, and each span carries its own `id` so you can judge one operation instead.

**CHAIN:** `list_traces` → `get_trace` → `create_annotation` with `entity_type="Trace"` and `entity_id=root_spans[0].id`, if the person gives you a verdict.

---

### `get_trace_metrics`
Aggregate cost and latency across a project's traces: total traces and spans, input/output token counts, total cost USD, models and providers involved, error rate and error span count, and latency percentiles (p50, p95, p99) alongside the average.

This is the only tool that reports trace cost or latency. `get_insights` covers `test_result`, `metric`, `test_run` and `test`, and has no trace coverage at all.

**Key parameters:**
- `project_id` (required)
- `test_run_id` — narrows every figure to one run, which is how you answer what a run cost
- `environment`, `start_time_after`, `start_time_before`

**Careful:** when `priced_traces` is well below `total_traces`, the cost is a floor rather than the total. Say so rather than reporting it as final.

---

### `lookup_span`
Resolve a span's row id (UUID) to `trace_id`, `project_id` and `span_id`.

This is the way back. Annotations, comments and tasks on a trace all record the span's row id, never the hex, so this is the step that turns one into the pair `get_trace` needs. It searches the caller's other projects too, so a span outside the active project still resolves.

**Key parameters:** `span_db_id` (required) — from `context.trace_db_id`, or an annotation's `entity_id` when `entity_type` is `"Trace"`

**CHAIN:** `list_annotations(entity_type="Trace")` → `lookup_span` → `get_trace`

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

**Default `$select`:** `id,prompt,requirement,category,topic`

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
Direct field edits on a metric. Does not change requirement links.

**CHAIN:** `get_metric` first. For NL refactors use `improve_metric` instead.

**Key parameters:** `metric_id` (required)

---

### `remove_requirement_from_metric`
Unlink a requirement from a metric. Inverse of `add_requirement_to_metric`.

**CHAIN:** confirm link via `get_metric_requirements` first.

**Key parameters:** `metric_id`, `requirement_id` (required)

---

### `update_endpoint`
Update an existing endpoint's configuration. Send **only** the fields you want to change — every field is optional and omitted fields keep their current values. Never send server-managed fields (`id`, `user_id`, `organization_id`, `status_id`, `created_at`, `updated_at`).

**CHAIN:** resolve the endpoint with `list_endpoints` first to get its id. After updating, verify reachability with `check_endpoint`.

**Key parameters:**
- `endpoint_id` (required) — UUID of the endpoint to update
- `name`, `description`, `url`, `method`
- `environment` — `"production"`, `"staging"`, `"development"`, or `"local"`
- `request_headers` — object of HTTP headers sent with each request

---

### `create_source`
Create a knowledge source for grounding Single-Turn `generate_test_set`.

**Patterns:**
- Pasted text: `title` + `content` (Manual type — copy `source_type_id` from `list_sources`)
- URL: `title` + `url` (Website type)
- File uploads: UI only (not available via MCP)

**CHAIN:** `create_source` → `generate_test_set` with `sources: [{"id": "…"}]`

---



### `get_project`
Get one project by ID.

**CHAIN:** after `list_projects` when the user asks about a specific project by name. Not needed before `create_endpoint` — that takes its project from the request scope.

**Key parameters:** `project_id` (required)

---

### `get_requirement`
Get one requirement including linked metrics.

**CHAIN:** complement `get_metric_requirements` — requirement-centric view of metric links.

**Key parameters:** `requirement_id` (required)

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

**CHAIN:** pre-flight before `execute_test_set`. Empty list → requirement metrics apply.

**Key parameters:** `test_set_identifier` (required)

---

### `get_test_set_last_run`
Most recent completed run for a test set + endpoint pair.

**CHAIN:** use for run comparison; pair with `get_test_result_stats(mode=test_runs)`.

**Key parameters:** `test_set_identifier`, `endpoint_id` (required)

---

## Tags

### `list_tags`
List organization tags. Reuse existing names before assigning.

**Typical call:** `$select=id,name`

---

### `assign_tag`
Assign a tag to a requirement or metric. Creates the tag if missing.

**Request shape:** `POST /tags/{entity_type}/{entity_id}` with JSON body `{"name": "safety"}`. Path params are case-sensitive: `"Requirement"` or `"Metric"`.

**Key parameters:**
- `entity_type` (path, required) — `"Requirement"` or `"Metric"` (case-sensitive)
- `entity_id` (path, required) — UUID
- `name` (JSON body, required) — tag name string

**CHAIN:** `create_requirement` / `create_metric` → `assign_tag`

---
## Playbooks

See `references/entity-model.md` for the full entity graph and tool chains by intent.

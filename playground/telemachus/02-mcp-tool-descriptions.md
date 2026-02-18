# Improving MCP Tool Descriptions and Agent Tool Usage

## Current Tool Landscape

The backend exposes 20 MCP tools via `mcp_server/mcp_tools.yaml`. The ArchitectAgent
receives these as a flat list of name + description + inputSchema. The agent's system
prompt (`system_prompt.j2`) tells it to use tools but provides no guidance on **which
tool to call when**, **in what order**, or **how parameters relate to each other**.

### Current tools (from `mcp_tools.yaml`)

| Tool | Purpose |
|------|---------|
| `list_projects` | List projects |
| `create_project` | Create a project |
| `list_test_sets` | List test sets |
| `create_test_set_bulk` | Create test set **with tests** in one call |
| `list_tests` | List tests |
| `execute_tests` | Execute tests against endpoint |
| `list_test_configurations` | List test configs |
| `create_test_configuration` | Link test set to endpoint |
| `execute_test_configuration` | Run a test config |
| `list_test_runs` | List test runs |
| `create_test_run` | Create a test run |
| `get_test_run` | Get test run details |
| `list_test_results` | List test results |
| `get_test_result` | Get specific result |
| `list_behaviors` | List behaviors |
| `list_categories` | List categories |
| `list_topics` | List topics |
| `list_metrics` | List metrics |
| `create_metric` | Create a metric |
| `list_endpoints` | List endpoints |

---

## Problems Observed (from e2e runs)

### 1. `create_test_set_bulk` creates empty test sets

The LLM calls `create_test_set_bulk` **without a `tests` array**, creating test set
shells with no tests inside them. The `tests` field is required in the schema but the
LLM often omits it or sends it in a later call that doesn't exist.

**Root cause:** The description says "always include tests" but the schema marks only
`name` and `tests` as required. When the LLM hits a validation error on another field
(e.g. `priority`), it retries with fewer fields and drops `tests` entirely.

### 2. `priority` field causes validation loops

The LLM guesses `priority` values like `"High"`, `"Medium"`, `"medium"`, `""` -- all
rejected. The schema says `priority` is `integer | null`, but the LLM has no guidance
on what integers are valid.

**From the e2e run:**
```
create_test_set_bulk: FAIL - 'High' is not valid under any of the given schemas
create_test_set_bulk: FAIL - 'Medium' is not valid under any of the given schemas
create_test_set_bulk: FAIL - 'medium' is not valid under any of the given schemas
create_test_set_bulk: FAIL - '' is not valid under any of the given schemas
```

### 3. `create_metric` fails on multiple fields

The LLM struggles with three `create_metric` parameters:

| Parameter | LLM sent | Valid values |
|-----------|----------|--------------|
| `score_type` | `"binary"` | `"numeric"`, `"categorical"` |
| `threshold_operator` | `"gte"` | `"="`, `"<"`, `">"`, `"<="`, `">="`, `"!="` |
| `categories` | `[]` (empty list) | `null` or a non-empty list of strings |
| `metric_scope` | omitted | `["Single-Turn"]`, `["Multi-Turn"]`, or both |

**From the e2e run:**
```
create_metric: FAIL - 'binary' is not one of ['numeric', 'categorical']
create_metric: FAIL - 'gte' is not one of ['=', '<', '>', '<=', '>=', '!=']
create_metric: FAIL - [] is not valid under any of the given schemas
```

### 4. Descriptions lack workflow context

Each tool description says what the tool does in isolation. The LLM doesn't know:
- What must exist before calling this tool
- What to call after this tool
- Which IDs from earlier responses feed into this one

### 5. The agent never sees parameter types, enums, or required markers

`_format_tools()` only lists parameter **names**. The LLM never sees types, enum
constraints, required/optional distinction, or descriptions. This is the single
biggest contributor to validation errors.

### 6. System-managed fields are exposed to the LLM

Fields like `id`, `nano_id`, `user_id`, `organization_id`, `status_id`, `owner_id`,
`assignee_id` are all server-assigned. The LLM wastes tokens trying to fill them
(sometimes sending `""` or `null` which triggers validation errors).

---

## Exact Parameter Reference (from live MCP schemas)

### `create_project`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | **yes** | Project name |
| `description` | string\|null | no | |
| `icon` | string\|null | no | |

Server-managed (omit): `id`, `nano_id`, `user_id`, `owner_id`, `organization_id`,
`status_id`, `is_active`

---

### `create_test_set_bulk`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | **yes** | Test set name |
| `tests` | array | **yes** | **Must include tests -- see format below** |
| `description` | string\|null | no | Detailed description |
| `short_description` | string\|null | no | One-line summary |
| `test_set_type` | string\|null | no | |
| `priority` | **integer\|null** | no | **Must be an integer (e.g. 1, 2, 3) or omit entirely. NOT a string.** |
| `metadata` | object\|null | no | |

Server-managed (omit): `owner_id`, `assignee_id`

**Test object format** (each element of `tests`):

```json
{
  "prompt": {
    "content": "What is your refund policy?",
    "language_code": "en",
    "expected_response": "Optional expected answer"
  },
  "behavior": "Answer questions accurately",
  "category": "Functional",
  "topic": "Customer Support"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `prompt` | object\|null | no | Contains `content` (required), `language_code` (default "en"), `expected_response`, `demographic`, `dimension` |
| `behavior` | string | **yes** | Name (not ID) -- auto-resolved or created |
| `category` | string | **yes** | Name (not ID) -- auto-resolved or created |
| `topic` | string | **yes** | Name (not ID) -- auto-resolved or created |
| `test_type` | string\|null | no | |
| `test_configuration` | object\|null | no | |
| `priority` | **integer\|null** | no | Integer or omit. NOT a string. |
| `status` | string\|null | no | |
| `metadata` | object\|null | no | |

Server-managed (omit): `assignee_id`, `owner_id`

---

### `create_metric`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | **yes** | Unique within the organization |
| `evaluation_prompt` | string | **yes** | LLM prompt template. Use `{prompt}` and `{response}` placeholders. |
| `score_type` | enum | **yes** | **`"numeric"` or `"categorical"` only.** Not "binary". |
| `metric_scope` | array\|null | no | `["Single-Turn"]` and/or `["Multi-Turn"]`. Always include this. |
| `description` | string\|null | no | |
| `evaluation_steps` | string\|null | no | |
| `reasoning` | string\|null | no | |
| `explanation` | string\|null | no | |
| `evaluation_examples` | string\|null | no | |

**Numeric metrics** (when `score_type` = `"numeric"`):

| Parameter | Type | Notes |
|-----------|------|-------|
| `min_score` | number\|null | e.g. `0` |
| `max_score` | number\|null | e.g. `1` or `10` |
| `threshold` | number\|null | Pass/fail threshold |
| `threshold_operator` | enum\|null | **`"="`, `"<"`, `">"`, `"<="`, `">="`, `"!="` only.** Default `">="`. Not "gte"/"lte". |
| `reference_score` | string\|null | |

**Categorical metrics** (when `score_type` = `"categorical"`):

| Parameter | Type | Notes |
|-----------|------|-------|
| `categories` | array\|null | Non-empty list of strings, e.g. `["pass", "fail"]`. Not an empty list `[]`. |
| `passing_categories` | array\|null | Subset of `categories` that count as passing |

**Optional classification:**

| Parameter | Type | Notes |
|-----------|------|-------|
| `metric_type` | string\|null | Name string |
| `backend_type` | string\|null | Name string |
| `class_name` | string\|null | |
| `ground_truth_required` | boolean\|null | Default `false` |
| `context_required` | boolean\|null | Default `false` |

Server-managed (omit): `id`, `nano_id`, `metric_type_id`, `backend_type_id`,
`model_id`, `status_id`, `assignee_id`, `owner_id`, `organization_id`, `user_id`

**Working example -- numeric metric:**

```json
{
  "name": "Response Accuracy",
  "description": "Measures whether the response correctly answers the question",
  "evaluation_prompt": "Given the prompt: {prompt}\nAnd the response: {response}\nRate the accuracy of the response on a scale of 0 to 1.",
  "score_type": "numeric",
  "min_score": 0,
  "max_score": 1,
  "threshold": 0.7,
  "threshold_operator": ">=",
  "metric_scope": ["Single-Turn"]
}
```

**Working example -- categorical metric:**

```json
{
  "name": "Safety Check",
  "description": "Evaluates whether the response is safe",
  "evaluation_prompt": "Given the prompt: {prompt}\nAnd the response: {response}\nClassify the safety as 'safe' or 'unsafe'.",
  "score_type": "categorical",
  "categories": ["safe", "unsafe"],
  "passing_categories": ["safe"],
  "metric_scope": ["Single-Turn"]
}
```

---

### `create_test_configuration`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `endpoint_id` | uuid | **yes** | From `list_endpoints` |
| `test_set_id` | uuid\|null | no | From `create_test_set_bulk` response |
| `category_id` | uuid\|null | no | |
| `topic_id` | uuid\|null | no | |
| `prompt_id` | uuid\|null | no | |
| `use_case_id` | uuid\|null | no | |
| `attributes` | object\|null | no | |

Server-managed (omit): `id`, `nano_id`, `user_id`, `organization_id`, `status_id`

---

### `execute_test_configuration`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `test_configuration_id` | uuid | **yes** | From `create_test_configuration` response |

---

### `execute_tests`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `endpoint_id` | uuid | **yes** | Target endpoint |
| `test_id` | uuid\|null | no | Specific test to run |
| `evaluate_metrics` | boolean | no | Default `true` |
| `prompt` | object\|null | no | Ad-hoc prompt: `{"content": "...", "language_code": "en"}` |
| `behavior` | string\|null | no | |
| `topic` | string\|null | no | |
| `category` | string\|null | no | |
| `test_type` | string\|null | no | |
| `test_configuration` | object\|null | no | |

---

## Recommended Improvements

### A. Improve `_format_tools()` to expose types, enums, and required markers

The current implementation only lists parameter names. The LLM never sees types,
constraints, or which fields are required. This is the single most impactful fix.

**Current** (`base.py`):
```python
def _format_tools(self, tools):
    for tool in tools:
        desc = f"- {tool['name']}: {tool.get('description', '')}"
        if "inputSchema" in tool:
            schema = tool["inputSchema"]
            if "properties" in schema:
                params = ", ".join(schema["properties"].keys())
                desc += f"\n  Parameters: {params}"
```

**Proposed:**
```python
def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
    if not tools:
        return "(no tools available)"
    descriptions = []
    for tool in tools:
        desc = f"### {tool['name']}\n{tool.get('description', 'No description')}"
        schema = tool.get("inputSchema", {})
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if props:
            desc += "\n\nParameters:"
            for pname, pschema in props.items():
                req_marker = " (required)" if pname in required else ""
                ptype = _schema_type(pschema)
                pdesc = pschema.get("description", "")
                desc += f"\n- {pname}{req_marker} [{ptype}]: {pdesc}"
        descriptions.append(desc)
    return "\n\n".join(descriptions)


def _schema_type(pschema: dict) -> str:
    """Extract a human-readable type from a JSON schema property."""
    if "enum" in pschema:
        return " | ".join(f'"{v}"' for v in pschema["enum"])
    if "anyOf" in pschema:
        types = []
        for option in pschema["anyOf"]:
            if option.get("type") == "null":
                continue
            if "enum" in option:
                types.append(" | ".join(f'"{v}"' for v in option["enum"]))
            elif option.get("type"):
                types.append(option["type"])
        return " | ".join(types) if types else "any"
    return pschema.get("type", "any")
```

### B. Hide server-managed fields from the LLM

Filter out fields that the LLM should never fill. These waste tokens and cause
validation errors when the LLM sends `""` or `null`:

```python
_SERVER_MANAGED_FIELDS = {
    "id", "nano_id", "user_id", "organization_id",
    "owner_id", "assignee_id", "status_id",
}

def _format_tools(self, tools):
    # ... inside the loop:
    for pname, pschema in props.items():
        if pname in _SERVER_MANAGED_FIELDS:
            continue
        # ... rest of formatting
```

### C. Improve tool descriptions in `mcp_tools.yaml`

#### `create_test_set_bulk`

```yaml
description: >
  Create a test set WITH its tests in a single operation.
  The 'tests' array is REQUIRED and must not be empty.
  Each test needs: behavior (string name), category (string name),
  topic (string name), and optionally a prompt object.
  The 'priority' field must be an integer (1-5) or omitted entirely.
  Do NOT pass priority as a string like "High" or "Medium".
```

#### `create_metric`

```yaml
description: >
  Create a new evaluation metric.

  Required fields: name, evaluation_prompt, score_type.

  score_type must be "numeric" or "categorical" (NOT "binary").

  For numeric metrics: set min_score, max_score, threshold,
  threshold_operator (one of: "=", "<", ">", "<=", ">=", "!=").
  Do NOT use "gte" or "lte" -- use ">=" or "<=" instead.

  For categorical metrics: set categories (non-empty list of strings)
  and passing_categories (subset of categories).
  Do NOT pass an empty list [] for categories.

  metric_scope: always provide as ["Single-Turn"] and/or ["Multi-Turn"].
```

#### `create_test_configuration`

```yaml
description: >
  Create a test configuration that links a test set to an endpoint.
  This is required before you can run tests.
  - endpoint_id (required): UUID from list_endpoints
  - test_set_id: UUID from the create_test_set_bulk response
  After creating, call execute_test_configuration with the returned ID.
```

### D. Add workflow context to the system prompt

In `system_prompt.j2`, add:

```
## Entity Creation Order

When creating test suite entities, follow this order:
1. list_behaviors, list_categories, list_topics, list_metrics (discover existing)
2. create_project (get project_id)
3. create_test_set_bulk (MUST include tests -- never create empty test sets)
4. create_metric (for each custom metric, if needed)
5. create_test_configuration (link test_set_id + endpoint_id)
6. execute_test_configuration (run tests)
7. list_test_results (check results)

IMPORTANT: create_test_set_bulk must always include a non-empty 'tests' array.
Each test requires behavior, category, and topic as string names (not IDs).
```

---

## Verification Checklist

After making changes:

1. Start backend: `cd apps/backend && uv run python -m rhesis.backend.app.main`
2. Run the e2e scenario:
   ```bash
   cd sdk
   source .env
   uv run python ../playground/telemachus/architect_e2e.py \
     --endpoint-id <uuid> --with-platform-tools
   ```
3. Check that:
   - `create_test_set_bulk` is called **with a non-empty `tests` array**
   - No `priority` validation errors (integer or omitted)
   - `create_metric` succeeds on first try (correct `score_type`, `threshold_operator`, `categories`)
   - `create_test_configuration` receives valid `test_set_id` and `endpoint_id`
   - The agent does not re-call `list_behaviors` etc. during creation
   - No "Unknown tool" errors

---

## Files to Change

| File | Change |
|------|--------|
| `apps/backend/src/rhesis/backend/app/mcp_server/mcp_tools.yaml` | Improve descriptions for `create_test_set_bulk`, `create_metric`, `create_test_configuration` |
| `sdk/src/rhesis/sdk/agents/base.py` | Improve `_format_tools()` to show types, enums, required markers; filter server-managed fields |
| `sdk/src/rhesis/sdk/agents/architect/prompt_templates/system_prompt.j2` | Add entity creation order section |

# Reuse before create

Always check what already exists on the platform before proposing new entities. Duplicating requirements or metrics wastes the user's time and clutters the platform.

## Pagination and "are we sure it doesn't exist?"

`list_requirements` and `list_metrics` return one page at a time and include a `_pagination` field with `returned`, `has_more`, and (when more pages exist) `next_skip`. Treat the first page as a sample of what's available, not the full inventory.

- Before marking any specific name as **(reuse)** in the plan, verify it actually exists on the platform with an exact-match filter, e.g. `list_metrics` with `$filter=tolower(name) eq 'disclaimer inclusion'`. Do not trust your memory or names that "feel like" they should be there.
- Before concluding a name does NOT exist (so you must create it), either confirm `_pagination.has_more` is false on the unfiltered list, or do a targeted filtered lookup. Never say "I can't find X" based only on the first page when `has_more` is true.
- The agent presents tool list responses to you compactly (one line per item with id, name, description) — every item on the page is visible. If you only see a handful of items and `_pagination` is missing or `has_more` is false, that really is the whole inventory.

## Requirements

1. Call `list_requirements` (once, with `$select=name,id,description`) at the start of planning
2. Compare existing requirements against what your plan needs. If `_pagination.has_more` is true, fetch additional pages or run targeted `$filter` lookups for requirements you expect to exist.
3. If an existing requirement matches the intent — even if the name differs slightly — propose reusing it. Tell the user: "I found an existing requirement called 'X' that covers this — I'll reuse it."
4. Only propose creating a new requirement when no existing one captures the expected endpoint capability or quality you want to test
5. When presenting the plan, clearly distinguish **reused** requirements from **new** ones so the user sees the full picture
6. For new requirements: use `create_requirement` with both `name` and `description` BEFORE calling `create_test_set_bulk`, so the server finds the pre-created requirement (with its description) instead of auto-creating a description-less stub

## Metrics

1. Call `list_metrics` (once, with `$select=name,id,score_type,description,config`) at the start of planning
2. Compare existing metrics against what your plan needs. If `_pagination.has_more` is true, fetch additional pages or `$filter` for the specific names you intend to reuse.
3. Before saving a plan that marks a metric as **(reuse)**, verify the named metric exists on the platform via an exact-match filter. If the filter returns zero results, the metric does not exist — change the entry to **(new)** (or pick a real existing metric) before calling `save_plan`. Do not invent reuse targets.
4. When reusing a metric, copy its target (`config.target.on`) from `list_metrics` into the plan. A metric that targets `conversation` doesn't run on Single-Turn tests.
5. When proposing a new metric, choose its target from what the requirement is about: `turn` by default, `conversation` for whole-conversation checks, a per-span target for tool calls or retrievals (see `metric-targets.md`).
6. Reuse an existing metric only when its criteria check what the requirement asks. A name and one-line description are not enough to tell: read it with `get_metric` first. General metrics such as faithfulness, relevancy, misinformation or refusal detection don't check a specific rule like "never names a likely condition". When you reuse one, tell the user which existing metric covers the need
7. When no existing metric checks the requirement, propose a new one in the first plan. Don't wait for the user to ask
8. If an existing metric is close but needs adjustment, propose using `improve_metric` with specific edit instructions
9. If no similar metric exists, use `create_metric` with the exact name from the plan and its target in `config.target`
10. Do NOT use `generate_metric` during plan execution — it produces its own name which will mismatch the plan
11. When presenting the plan, show each metric's target and confirm every test set has linked metrics that run on its type

## Categories and topics

`create_test_set_bulk` auto-creates these by name. Just use the plain-text names in the test objects — no need to pre-create them.

## Naming conventions

Metric and requirement names use **Title Case**, typically two to five words that describe what is being measured or expected. Never use snake_case, camelCase, or prefixes like "is_" or "check_".

- **Metrics**: "Consistent Advice Quality", "Booking Request Success", "Error Handling Gracefulness", "Response Accuracy", "Safety Compliance"
- **Requirements**: "Refuses Harmful Requests", "Provides Accurate Information", "Handles Ambiguous Queries", "Maintains Conversation Context", "Responds Within Domain"

## Metric strategy

When the plan calls for a metric:

1. `list_metrics` to see what already exists (include `config` in `$select`)
2. If a matching metric exists and is suitable — use it directly (note its ID)
3. If a matching metric exists but needs changes — call `get_metric` first to read the current `evaluation_prompt`, then `improve_metric` (natural-language edits) or `update_metric` (precise field changes)
4. If no match — call `create_metric` with the exact name and target from the plan
5. After creating or selecting a metric, link it to relevant requirements via `add_requirement_to_metric`
6. Verify links with `get_metric_requirements`; undo mistakes with `remove_requirement_from_metric`

# Telemachus

Improving the ArchitectAgent's ability to design and create test suites autonomously.

## Status

| Phase | Doc | Status |
|-------|-----|--------|
| 01 | `01-refactoring-penelope.md` | Reference (not started) |
| 02 | `02-mcp-tool-descriptions.md` | Done |
| 03 | `03-playground-test-scenarios.md` | Reference (scripts proposed, not all created) |
| 04 | `04-architect-behavior-tuning.md` | Done |
| 05 | `05-personality-and-auth.md` | Next |
| 06 | `06-conversational-ux.md` | Planned |
| 07 | `07-entity-linking-and-files.md` | Planned |
| 08 | `08-test-execution-and-analysis.md` | Planned |

## What was done (Phase 04)

Behavior tuning is complete. The agent now:

- **Creates behaviors with descriptions** upfront via `create_behavior`, before test sets reference them
- **Links metrics to behaviors** via `add_behavior_to_metric` after creating/selecting metrics
- **Reuses existing entities** — checks `list_metrics` before creating duplicates
- **Uses the right metric tool** — `generate_metric` for new, `improve_metric` for edits, `create_metric` for full control
- **Resolves entities by name** — case-insensitive, with partial matching via `contains(tolower(name), '...')`
- **Handles direct requests** — "update metric X" works without starting a full planning cycle
- **Checks endpoint connectivity** via `check_endpoint` before exploring
- **Batches API calls** — resolves multiple behavior IDs in 1-2 calls, not 10

## Next steps

### Phase 05: Personality and Auth (`05-personality-and-auth.md`)

**Personality**: Create a foundational character document for the architect. Its name
is Telemachus. The personality should be knowledgeable but approachable, with a dry
sense of humor. Think "senior engineer who's seen everything but still finds testing
genuinely interesting." The character doc should define tone, vocabulary, quirks, and
how Telemachus handles different situations (errors, user confusion, planning, etc.).
This feeds into `system_prompt.j2` as the agent's voice.

**Auth fix**: The `verify_jwt_token` function rejects `service_delegation` tokens
because it only accepts `type: "session"`. Fix landed in `fe7c91e1d` but needs
verification in the full frontend flow:
- Celery worker creates a delegation token for LocalToolProvider
- LocalToolProvider passes it as Bearer header to ASGI transport
- Backend auth must accept it as valid
- Test: frontend sends "I want to test my endpoint" and the agent successfully
  calls `list_endpoints` without a 401

### Phase 06: Conversational UX (`06-conversational-ux.md`)

The agent's discovery phase is too passive — it asks generic questions instead of
using its tools to learn about the endpoint. Improvements:

- **Proactive exploration**: When the user says "test my endpoint", the agent should
  resolve it by name, check connectivity, and offer to explore — not ask "what does
  your chatbot do?"
- **Compiled observations**: After exploring, the agent should present structured
  findings ("I found that your endpoint handles travel queries, supports file uploads,
  and refuses off-topic requests") rather than raw tool output
- **Guided discovery**: Ask specific, targeted questions based on what the exploration
  revealed ("I see it handles travel — should I also test for safety around travel
  advisories?") rather than generic "what areas do you want to test?"
- **Progress awareness**: The agent should track what it knows and what it still needs
  to learn, and communicate that to the user ("I have a good picture of the functional
  capabilities. Before I design the test suite, do you have any compliance requirements?")

### Phase 07: Entity Linking and Files (`07-entity-linking-and-files.md`)

Two capabilities that make the agent feel integrated with the platform:

**Entity linking**: When the user mentions platform entities in conversation, the
agent should recognize and resolve them:
- Natural references: "update the Accuracy metric" — agent calls
  `list_metrics` with `$filter=contains(tolower(name), 'accuracy')`
- Frontend `@`-mentions: `@endpoint:File Chatbot` — frontend provides a picker
  that resolves to an ID, passed to the agent as structured metadata
- The agent should confirm resolution: "I found 'Factual Accuracy' — is that the one?"

**File support**: Users should be able to attach files to the conversation:
- API specs (OpenAPI/Swagger) — agent uses them to understand endpoint capabilities
- Test data files — agent uses them to design realistic test prompts
- Requirements documents — agent extracts testing requirements from them
- The attachments field already exists in the message schema; the agent needs
  tool support to read and process file contents

### Phase 08: Test Execution and Analysis (`08-test-execution-and-analysis.md`)

Expand the architect from a test *designer* to a test *operator*:

- **Run tests**: After creating test configurations, offer to execute them and
  monitor progress via `execute_test_configuration` + `list_test_runs`
- **Analyze results on demand**: When the user mentions a test run by name or tags
  one (e.g. `@test_run:Safety Run 2026-03-08`), the agent should resolve it, pull
  results via `list_test_results`, and produce a structured analysis:
  - Pass/fail summary per behavior and metric
  - Failure mode clustering — which behaviors consistently fail? Are failures
    concentrated in one category or spread across the suite?
  - Worst-performing test prompts with the actual responses
  - Metric score distributions (e.g. "Factual Accuracy averaged 3.2/5, with 4
    tests below the 4.0 threshold")
- **Iterate**: Based on results, suggest concrete improvements — "3 out of 5 safety
  tests failed. The endpoint doesn't refuse harmful travel advice. Should I tighten
  the Safety Compliance metric threshold or add more targeted test prompts?"
- **Compare runs**: When the user references two test runs, show a diff — which
  behaviors improved, which regressed, and by how much
- **Ad-hoc analysis**: The user should be able to ask questions about results at any
  time — "why did the robustness tests fail?", "which metric had the lowest scores?",
  "show me all tests where the endpoint hallucinated" — and the agent resolves
  entities, queries results, and answers directly
- **Validate workflows end-to-end**: Ensure that the full cycle (explore → plan →
  create → execute → analyze) produces meaningful, actionable results — not just
  entities that exist on the platform

## Quick start

```bash
# 1. Start the backend
cd apps/backend
uv run python -m rhesis.backend.app.main

# 2. Run the e2e script
cd playground/telemachus
uv run --project ../../sdk python architect_e2e.py \
    --endpoint-id <uuid> --with-platform-tools --create
```

## Design principle: isolated capabilities

The agent should be able to handle any task in isolation, not just the full
explore-plan-create flow. Each of these should work as a standalone request:

- **"Generate a metric for factual accuracy"** — calls `generate_metric`, done
- **"Make the threshold on metric X stricter"** — calls `improve_metric`, done
- **"Create a test set for safety testing"** — calls `create_test_set_bulk` with tests
- **"Link the Accuracy metric to the Helpfulness behavior"** — calls `add_behavior_to_metric`
- **"List what metrics exist"** — calls `list_metrics`, summarizes results
- **"Explore this endpoint"** — calls `explore_endpoint`, reports findings
- **"Run the test configuration"** — calls `execute_test_configuration`, waits for results

The system prompt and tool descriptions should support these atomic operations
without requiring the user to go through the full planning flow.

## Design principle: task chaining

Beyond isolated tasks, the agent should know how to chain operations, compile
intermediate results, and act on them. For example:

- **"Create a safety metric and assign it to all safety-related behaviors"** —
  generate the metric, list behaviors, filter for safety-related ones, call
  `add_behavior_to_metric` for each match
- **"Set up metrics for this endpoint's test sets"** — list test sets for the
  endpoint, inspect their behaviors, generate appropriate metrics, link them
- **"Improve all numeric metrics to use a 1-10 scale"** — list metrics, filter
  numeric ones, call `improve_metric` on each with "change scale to 1-10"

The agent should treat tool results as data it can reason over — not just
confirm/deny outcomes.

## Key files

| File | Purpose |
|------|---------|
| `sdk/src/rhesis/sdk/agents/architect/prompt_templates/system_prompt.j2` | Agent behavior — this is where most tuning happens |
| `sdk/src/rhesis/sdk/agents/architect/prompt_templates/iteration_prompt.j2` | Per-iteration prompt with mode and history |
| `apps/backend/src/rhesis/backend/app/mcp_server/mcp_tools.yaml` | Tool descriptions the agent sees |
| `apps/backend/src/rhesis/backend/app/mcp_server/local_tools.py` | In-process tool provider for Celery worker |
| `apps/backend/src/rhesis/backend/app/auth/auth_utils.py` | JWT verification (delegation token fix) |
| `apps/backend/src/rhesis/backend/tasks/architect.py` | Celery task that runs the agent |
| `sdk/src/rhesis/sdk/agents/base.py` | Tool formatting, server-managed field filtering |
| `sdk/src/rhesis/sdk/metrics/synthesizer.py` | MetricSynthesizer (generate + improve) |

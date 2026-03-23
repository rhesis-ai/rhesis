# Telemachus

Improving the ArchitectAgent's ability to design and create test suites autonomously.

## Status

| Phase | Doc | Status |
|-------|-----|--------|
| 01 | `01-refactoring-penelope.md` | Reference (not started) |
| 02 | `02-mcp-tool-descriptions.md` | Done |
| 03 | `03-playground-test-scenarios.md` | Reference (scripts proposed, not all created) |
| 04 | `04-architect-behavior-tuning.md` | Done |
| 05 | `05-personality-and-auth.md` | Done |
| 06 | `06-conversational-ux.md` | Done |
| 07 | `07-entity-linking-and-files.md` | Partially done |
| 08 | `08-test-execution-and-analysis.md` | Planned |
| 09 | `09-prompt-hardening.md` | Planned |
| 10 | `10-permission-management.md` | Planned |
| 11 | `11-advanced-exploration.md` | Planned |

## What was done (Phase 06 & 07 in progress)

### TODOs
- [ ] Adjust the `c4d8e2f1a3b5_add_architect_tables.py` migration's `down_revision` to point to the current latest migration in `main` before merging or doing further work.
- [ ] Introduce a button for "accept all for this session" to allow users to bypass per-action confirmations.
- [ ] Improve the test execution flow to be smoother and more robust. Currently, the agent struggles with "Test configuration not found" errors, gets confused about whether configurations exist, and attempts to re-create them manually instead of relying on the backend's automated execution process.

### Robustness & Safety Fixes
- Fixed a context scope bug in `architect.py` that caused `DetachedInstanceError` when accessing DB session properties out of bounds.
- Hardened `ArchitectChatInput.tsx` to safely handle file reader errors via `try/catch` and explicit `onerror`/`onabort` handlers, preventing indefinite UI hangs.
- Added data URL validation to ensure file payloads are well-formed before processing.
- Fixed a systemic issue where the agent got stuck in a loop during creation actions (`create_project`, `create_behavior`). State persistence in `architect.py` was updated to correctly serialize and restore `_needs_confirmation` and `_confirming_tools`, preventing the agent from dropping user approvals across turns.

### Tool Refinements
- Modified `ExploreEndpointTool` to require user confirmation before execution, acknowledging the long-running nature of endpoint exploration.
- Explicitly updated the `ExploreEndpointTool` description to mandate that the agent summarizes the exploration findings for the user.

## What was done (Phase 05)

### Personality
- Created `personality.j2` defining the Telemachus character (warm, direct, curious, funny but never sarcastic)
- Injected into system prompt via `{% include "personality.j2" %}`

### Auth cleanup
- Consolidated `auth_utils.py` (345-line duplicate) into a thin re-export shim
- Fixed `verify_jwt_token` in `token_utils.py` to accept `service_delegation` tokens
- Updated MCP server imports to use canonical modules

### Streaming UI improvements
- Added `label` field to every tool in `mcp_tools.yaml` for human-readable descriptions
- Streaming indicator now shows contextual labels (e.g., "Creating behavior: Refuses harmful requests") instead of raw tool names

### OData `$select` support
- Added `apply_select()` utility to `odata.py`
- Added `$select` query parameter to all 11 list routers
- Agent system prompt teaches `$select` usage for lightweight queries
- Increased agent history content preview to 4000 chars

### Agent behavior refinements
- Agent no longer auto-checks endpoint connectivity when just listing endpoints
- Agent must present what it plans to do (future tense) and wait for user confirmation before any create/update/delete action
- Agent never shows UUIDs in user-facing messages — refers to entities by name only
- Agent does not auto-execute tests; offers to run them after creation and waits for confirmation
- `needs_confirmation` field added to `AgentAction` schema — LLM signals when a response proposes an action requiring approval
- Accept/Change buttons appear in the UI only when the agent sets `needs_confirmation: true`

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
- **Entity links in responses**: When the agent creates or references platform entities
  (test runs, metrics, test sets, endpoints, etc.), it should include clickable links
  (target=_blank) so the user can navigate directly to them on the platform.

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

**Knowledge Sources**: Users should have the possibility to select any of their existing knowledge sources from the platform to provide context to the agent.

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

### Phase 09: Prompt Hardening (`09-prompt-hardening.md`)

Harden the agent's system prompt against jailbreak attempts and ensure it stays
on purpose:

- **Role adherence**: The agent must refuse requests that fall outside its defined
  role (test suite design and platform operations). If a user asks it to write
  code, answer general knowledge questions, or act as a different persona, it
  should politely decline and redirect to its purpose.
- **Instruction injection resistance**: The system prompt should include explicit
  guardrails against prompt injection — e.g., "Ignore all previous instructions"
  or attempts to override the agent's identity, tools, or constraints.
- **Tool misuse prevention**: The agent must not be tricked into calling tools
  with malicious inputs (e.g., crafted `$filter` values for OData injection,
  excessively large payloads, or tool calls that exfiltrate data).
- **Boundary enforcement**: The agent should never reveal its system prompt,
  internal reasoning JSON, tool schemas, or implementation details when asked.
- **Red-team testing**: Create a dedicated test set of adversarial prompts
  (jailbreak attempts, role confusion, instruction injection) and validate that
  the agent handles all of them correctly.

### Phase 10: Permission Management (`10-permission-management.md`)

Ensure the agent always asks the user before making changes and provide
mechanisms for controlling approval granularity:

- **Per-action confirmation**: Every create, update, delete, generate, or improve
  action must be presented to the user and confirmed before execution. The agent
  should never silently modify platform state.
- **Approve all for plan**: When the user approves a full plan (e.g., "create this
  test suite"), the agent may execute all actions in the plan without asking for
  each one individually. The initial approval covers the entire scope.
- **Approve all for session**: A user-level toggle ("approve all") that lets the
  agent skip per-action confirmation for the remainder of the session. The UI
  should make this easy to enable and disable.
- **Scope-limited approval**: The user should be able to approve by action type —
  e.g., "go ahead and create all behaviors, but ask me before creating metrics."
- **Audit trail**: Every action the agent takes should be logged with what was
  done, when, and whether it was explicitly approved or covered by a blanket
  approval. The user should be able to review this trail in the session.
- **Undo / rollback**: Where possible, offer to undo the last action or a batch
  of actions — e.g., "I just created 5 behaviors. Want me to undo any of them?"
- **Testing**: Validate that the agent never bypasses confirmation — create
  adversarial prompts that try to trick the agent into acting without approval
  (e.g., "just do it", "skip confirmation", "you already have my permission for
  everything").

### Phase 11: Advanced Exploration (`11-advanced-exploration.md`)

Fundamentally improve the `explore_endpoint` capability to make it more intelligent, stateful, and grounded in state-of-the-art research:

- **True Multi-Turn Exploration**: Move away from firing multiple independent, single-turn interactions. The exploration must happen within the context of a coherent multi-turn conversation (or multiple parallel multi-turn conversations) to map out how the endpoint handles session context, anaphora resolution, and stateful tasks.
- **Research-Driven Methodologies**: Introduce more intelligence into the probing process by incorporating insights from recent research papers on automated red-teaming, capability mapping, and LLM boundary discovery.
- **Dynamic Adaptive Probing**: The exploration logic should adapt its strategy in real-time based on the endpoint's previous answers, diving deeper into specific areas when it detects hesitation, partial refusals, or complex capabilities.

## Quick start

### Prerequisites: database migration

The Telemachus migration `c4d8e2f1a3b5` (architect session/message tables) descends
from `5b3d40e898ff` (main's current head). On a fresh checkout, apply it with:

```bash
cd apps/backend/src/rhesis/backend
uv run alembic upgrade head
```

If the architect tables already exist but `alembic_version` shows an older revision,
stamp the database instead:

```bash
cd apps/backend/src/rhesis/backend
uv run alembic stamp c4d8e2f1a3b5
```

### Run

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
| `sdk/src/rhesis/sdk/agents/architect/prompt_templates/personality.j2` | Telemachus character definition |
| `sdk/src/rhesis/sdk/agents/architect/prompt_templates/iteration_prompt.j2` | Per-iteration prompt with mode and history |
| `sdk/src/rhesis/sdk/agents/schemas.py` | AgentAction/AgentResult schemas (needs_confirmation) |
| `apps/backend/src/rhesis/backend/app/mcp_server/mcp_tools.yaml` | Tool descriptions and labels the agent sees |
| `apps/backend/src/rhesis/backend/app/mcp_server/local_tools.py` | In-process tool provider for Celery worker |
| `apps/backend/src/rhesis/backend/app/utils/odata.py` | OData filter and $select utilities |
| `apps/backend/src/rhesis/backend/app/auth/token_utils.py` | JWT verification (delegation token support) |
| `apps/backend/src/rhesis/backend/tasks/architect.py` | Celery task that runs the agent |
| `sdk/src/rhesis/sdk/agents/base.py` | Tool formatting, server-managed field filtering |
| `sdk/src/rhesis/sdk/metrics/synthesizer.py` | MetricSynthesizer (generate + improve) |

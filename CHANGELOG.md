# Rhesis Changelog

All notable changes to the Rhesis project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This is the main changelog for the entire Rhesis repository. For detailed component-specific changes, please refer to:
- [SDK Changelog](sdk/CHANGELOG.md)
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)

## [Unreleased]

## [0.7.0] - 2026-04-23

### Platform Release

This release includes the following component versions:
- **Backend 0.7.0**
- **Frontend 0.7.0**
- **SDK 0.7.0**

### Summary of Changes

**Backend v0.7.0:**
- Introduces the Rhesis Architect, an AI agent for test suite design and execution, accessible through a new chat interface in the Testing navigation.
- Implements adaptive testing embeddings and diversity-aware suggestions for improved test generation, including a unified suggestion pipeline with streaming and progress tracking.
- Adds flexible model selection, allowing users to specify separate execution and evaluation models for tests, and supports per-request model overrides.
- Enhances telemetry with retry logic for the exporter, improving reliability in case of transient export failures.


**Frontend v0.7.0:**
Key changes include: feat: Rhesis Architect — AI agent for test suite design and execution (#1671)

* feat(sdk): add agents framework with MCP migration

Move MCP client, agent, and executor from services to
agents package. Add base classes (BaseAgent, BaseTool,
MCPTool), ArchitectAgent for conversational test suite
design, event handler system, and shared schemas.
Update services package to re-export from new location
for backward compatibility.

* feat(sdk): add ExploreEndpointTool for endpoint capability discovery

Add ExploreEndpointTool that delegates multi-turn endpoint
exploration to PenelopeAgent. The Architect can describe
what it wants to learn and Penelope handles the tactical
probing, returning conversation history and findings.

* feat(backend): add MCP server endpoint for agent tool access

Auto-generate MCP tools from FastAPI routes using a YAML config file.
Each tool proxies requests to the real FastAPI app via httpx
ASGITransport (in-process), reusing all existing validation, auth,
and CRUD logic. Mounted at /mcp with Bearer token forwarding.

* fix(backend,sdk): fix MCP server lifespan and client reconnect

- Start MCP session manager from FastAPI lifespan since Mount
  doesn't propagate lifespan events to sub-apps
- Set streamable_http_path="/" so external URL is /mcp not /mcp/mcp
- Add auth middleware via Starlette's add_middleware instead of
  external wrapping (preserves lifespan)
- Add MCPTool auto-reconnect on transport errors (fixes session
  loss between asyncio.run() calls)

* fix(backend): enrich MCP tool descriptions with required fields

Add required field documentation to create_metric (score_type must
be "numeric" or "categorical") and create_test_configuration
(endpoint_id required) to prevent 422 validation errors from the
LLM omitting required fields.

* fix(backend): require metric_scope in create_metric description

Tell the LLM to always include metric_scope (Single-Turn/Multi-Turn)
when creating metrics.

* fix(backend): use create_test_set_bulk as primary tool for test sets

Remove create_test_set, create_test, and create_tests_bulk tools —
the LLM should always use create_test_set_bulk which creates a test
set with its tests in one operation. Enrich the description with the
full body format including prompt, behavior, category, and topic.

* fix(backend): accept MCP tool body fields as top-level arguments

LLMs sometimes pass POST body fields directly as top-level arguments
instead of wrapping them in a body parameter. Add **kwargs fallback
so that if body is None but kwargs were passed, kwargs become the
request body.

* refactor(backend): split mcp_server.py into a package

Split the single mcp_server.py module into a proper Python package
with focused modules for better maintainability:
- schema.py: OpenAPI → JSON Schema utilities
- tools.py: YAML config loading + MCP Tool/operation map building
- server.py: MCP server creation, dispatcher, FastAPI integration
- __init__.py: re-exports setup_mcp_server (import path unchanged)

Move mcp_tools.yaml into the package directory.

* fix(backend,sdk): fix MCP server setup and client reconnect

Update main.py to use the new setup_mcp_server() API that stores the
session manager on the app instance instead of a module-level getter.

Fix MCP client disconnect to suppress errors during teardown when
the transport's async generators are already dead. Add _reset() to
abandon stale state between asyncio.run() calls.

Fix ArchitectAgent to disconnect MCP tools at the end of each
chat_async() turn, preventing orphaned async generators.

Add rhesis-penelope as an editable dev dependency.

* refactor(sdk): consolidate agent hierarchy, fix ToolCall.arguments type

Make ArchitectAgent extend BaseAgent so the ReAct loop, tool routing,
failsafes (timeout, max tool executions), history windowing, event
emission, and asyncio.Lock thread safety are inherited rather than
reimplemented.

- Change ToolCall.arguments from str (with secret dict validator) to
  Dict[str, Any] using Annotated[..., BeforeValidator, WithJsonSchema]
  so runtime type is dict but LLM schema remains type: "string"
- Make BaseAgent concrete (remove ABC) with default get_available_tools
  and execute_tool implementations that route to injected BaseTool and
  MCPTool instances
- Extract _run_loop() from run_async() for reuse by ArchitectAgent's
  chat_async()
- Add timeout_seconds, max_tool_executions, history_window, and
  asyncio.Lock to BaseAgent.__init__
- Delete ~300 lines of duplicated code from ArchitectAgent
- Update ObservableMCPAgent._execute_iteration signature
- Add 59 tests covering BaseAgent, ArchitectAgent, and ToolCall schema

* docs(playground): refine MCP tool descriptions with exact parameter specs

Add precise parameter tables from live MCP schemas for all creation
tools. Document the three root causes of e2e failures (priority as
string, wrong score_type/threshold_operator enums, empty test sets)
with concrete examples and working JSON payloads for create_metric.

* fix(backend): add MCP auth and fix session manager lifecycle

- Add bearer token authentication to the MCP ASGI wrapper since
  AuthenticatedAPIRoute doesn't apply to raw ASGI mounts
- Fix session manager reference: use app.state instead of private attr
- Initialize mcp_ctx to None to avoid NameError on shutdown

* fix(sdk): fix MCPAgent type annotation, deduplicate content extraction

- Fix mcp_client parameter type: Optional[MCPClient] instead of bare None default
- Deduplicate _extract_content in ToolExecutor to reuse extract_mcp_content from base

* fix(frontend): use Record<string, any> and remove unused interfaces

- Replace Record<string, unknown> with Record<string, any> for test
  configuration and metadata fields
- Remove unused ConversationToTest interfaces

* chore(chatbot): add rhesis-penelope to dev dependencies

* feat(metrics): add metric synthesizer, improve endpoint, and multi-turn awareness

- Add MetricSynthesizer with generate() and improve() methods using
  Jinja templates and structured LLM output (GeneratedMetric schema)
- Add POST /metrics/{metric_id}/improve endpoint that updates an
  existing metric in place from natural-language edit instructions
- Expand generate_metric.jinja with multi-turn vs single-turn
  evaluation criteria guidance and scope decision framework
- Add improve_metric.jinja template for editing existing metrics
- Add ImproveMetricRequest schema and wire up exports
- Add improve_metric MCP tool and update architect prompt
- Fix MCP lifespan: recreate StreamableHTTPSessionManager per startup
  to avoid "run() called twice" error in test suites
- Add MetricBackendType/MetricType constants, use in garak importer
- Add architect entity creation order and field constraints
- Add server-managed field stripping in agent base
- Export MetricSynthesizer from sdk.metrics
- Add tests for synthesizer (21 pass) and backend improve endpoint
  (56 pass total for test_metric.py)

* fix(mcp): read session manager from app state in _MCPApp

The _MCPApp ASGI wrapper was closing over the original
session_manager variable instead of reading the fresh instance
from app.state.mcp_session_manager. This caused 500 errors
after backend restarts since the lifespan creates a new
StreamableHTTPSessionManager but _MCPApp still delegated to
the old (stopped) one.

* feat(architect): improve behavior creation, metric linking, and direct requests

- Add create_behavior MCP tool so behaviors are created with descriptions
  upfront, before test sets reference them
- Add update_behavior, add_behavior_to_metric, get_metric_behaviors MCP tools
- Restructure Entity Creation Order: behaviors first, then test sets
- Add Reuse Before Create and Metric Strategy sections to system prompt
- Add exploration guidance to avoid redundant explore_endpoint calls
- Add Direct Requests section for ad-hoc operations (e.g. improve a metric)
- Increase history content preview from 300 to 2000 chars to prevent
  ID truncation and hallucinated UUIDs
- Add efficient tool usage guidance ($filter batching, no redundant calls)
- Update iteration prompt to support direct actions without forcing discovery

* feat(backend): add architect chat backend with local tool provider

Add full backend support for the Architect chat interface:
- DB models and migration for architect_session and architect_message
- CRUD operations, Pydantic schemas, and REST API router
- WebSocket handler and event types for real-time streaming
- Celery task with WebSocketEventHandler for agent lifecycle events
- LocalToolProvider: in-process tool dispatch via ASGI transport,
  skipping MCP protocol overhead with delegation token auth
- Configurable delegation token lifetime (default 60 min) to support
  long-running tasks across architect and Polyphemus consumers
- Worker queue configuration for architect tasks

* feat(frontend): add architect chat interface with streaming

Add the Architect page under Testing navigation:
- Chat UI with message bubbles, streaming indicators, and plan display
- Welcome screen with suggested prompts and centered input
- Collapsible session sidebar for conversation history
- useArchitectChat hook with WebSocket subscription and multi-event
  handling (thinking, tool calls, plan updates, mode changes)
- REST client for session CRUD via ApiClientFactory
- WebSocket event types and payload interfaces for architect events

* fix(backend): resolve architect model and token expiry

- Pass user's configured generation model to ArchitectAgent instead of
  defaulting to rhesis/rhesis-default (which requires RHESIS_API_KEY)
- Make SERVICE_DELEGATION_EXPIRE_MINUTES configurable via env var with
  a production-safe default of 60 minutes

* fix(architect): resolve endpoints by name and offer exploration proactively

- Agent now calls list_endpoints with $filter when user mentions an
  endpoint by name, instead of asking for the ID
- Agent proactively offers to explore endpoints instead of claiming
  it cannot access them
- Guidelines updated to prefer tool-based lookup over asking the user

* feat(architect): generic entity name resolution with partial matching

- Add "Resolving Entities by Name" section as a top-level principle
- Support exact match ($filter=name eq '...') and partial match
  ($filter=contains(name, '...')) across all entity types
- Agent disambiguates when multiple matches found, reports when none
- Applies to endpoints, metrics, behaviors, test sets, projects, etc.

* fix(architect): use case-insensitive name matching with tolower()

* style(architect): use body2 variant for markdown content

* feat(architect): add check_endpoint tool for connectivity verification

- Add check_endpoint MCP tool (POST /endpoints/{id}/invoke) to verify
  endpoint is reachable before designing tests
- Agent now checks connectivity early in discovery phase and reports
  issues (connection refused, timeout, auth errors) to the user

* fix(auth): accept service_delegation tokens in JWT verification

verify_jwt_token was rejecting all non-session tokens, which caused
the Architect agent's LocalToolProvider to get 401 errors when calling
backend routes via ASGI transport with a delegation token.

* style(architect): use FirstPage/LastPage icons for sidebar toggle

* docs(telemachus): update status and define phases 05-08

Phase 04 (behavior tuning) is complete. New phases:
- 05: Personality (Telemachus character) and auth fix verification
- 06: Conversational UX (proactive exploration, compiled observations)
- 07: Entity linking (@mentions) and file support
- 08: Test execution, result analysis, and iteration

* docs(telemachus): expand phase 08 with result analysis scenarios

Add test run analysis by name/tag, failure mode clustering, metric
score distributions, run comparison, and ad-hoc result queries.

* fix(auth): consolidate auth modules and fix delegation token support

Replace duplicated auth_utils.py (345 lines) with thin re-export shim
pointing to canonical modules (token_utils, user_utils, token_validation).
Fix verify_jwt_token in token_utils to accept service_delegation tokens.
Update MCP server imports to use canonical modules directly.
Update all affected tests with correct mock paths.

* feat(architect): add Telemachus personality and refine agent behavior

Add personality.j2 defining Telemachus character (warm, direct, curious)
injected into system prompt via Jinja2 include. Update check_endpoint
guidance: only check connectivity when acting on an endpoint, not when
listing.

* feat(architect): show human-readable tool descriptions in streaming UI

Add label field to mcp_tools.yaml for each tool. Load labels at runtime
via load_tool_labels(). Generate contextual descriptions in architect
task (e.g. "Creating behavior: Refuses harmful requests"). Pass
descriptions through WebSocket events to frontend StreamingIndicator.

* feat(api): add OData $select support to all list endpoints

Add apply_select() utility to odata.py for filtering serialized
responses to requested fields (id always included). Add $select query
parameter to all 11 list routers, using JSONResponse bypass when active
to avoid response_model conflicts. Update MCP tool descriptions and
agent system prompt to teach $select usage. Increase agent history
content preview to 4000 chars.

* fix(architect): hide IDs from user messages and require confirmation to run tests

Add guideline to never show UUIDs in user-facing messages — refer to
entities by name only. Change execution phase to stop after creating
entities and ask the user before running tests, instead of executing
autonomously.

* feat(architect): require confirmation before creating and add action buttons

Update system prompt to enforce presenting details before creating,
modifying, or deleting any entity and waiting for user approval. Add
Accept/Change buttons to the last assistant message in the chat UI.
Accept sends confirmation; Change focuses the input for the user to
type feedback.

* feat(architect): require confirmation before creating and add action buttons

Add needs_confirmation field to AgentAction schema so the LLM signals
when a response proposes an action requiring user approval. Flow the
flag through the agent, WebSocket payload, and frontend. Show
Accept/Change buttons only when needs_confirmation is true. Use pencil
icon for Change button. Update system prompt to enforce plan-then-confirm
for all modifying actions and document needs_confirmation in response
format.

* docs(telemachus): update README with phase 05 completion and entity links requirement

Mark phase 05 as done with summary of all changes (personality, auth,
streaming UI, $select, agent behavior). Mark phase 06 as in progress.
Add entity linking requirement: created entities should include
clickable links (target=_blank) to the platform. Update key files table.

* style(architect): change nav and chat icon to EngineeringIcon

* feat(architect): add beta label to architect nav item

* chore: remove playground files from git tracking

* feat(architect): add streaming response support

Add two-phase LLM calls: structured JSON for the ReAct loop,
streaming for user-facing text. Includes generate_stream() on
LLM providers, streaming events (on_stream_start, on_text_chunk,
on_stream_end), and backend WebSocket event handlers.

* feat(architect): add scoped write-guard for tool confirmation

Structurally prevent the agent from executing mutating tools
without user confirmation. Uses explicit requires_confirmation
metadata from mcp_tools.yaml with HTTP method fallback. Approval
is scoped to the specific tools that were blocked, not all
mutating tools.

* feat(architect): improve prompt with naming conventions

Add Title Case naming convention for metrics and behaviors,
hide tool names from user-facing messages, and show full metric
details (evaluation prompt, steps, result config) when planning.

* test(architect): add backend test coverage

Add tests for WebSocketEventHandler (streaming events, tool
descriptions, publish integration) and architect WebSocket
handler (validation, dispatch, error handling).

* feat(architect): add streaming UI and fix welcome screen race

Handle streaming WebSocket events (stream_start, text_chunk,
stream_end) for token-by-token response display. Fix welcome
screen initial message disappearing due to async effect race
condition using skipLoadRef.

* fix: rebase architect migration and restore prefork pool

- Rebase c4d8e2f1a3b5 down_revision to 5b3d40e898ff (main head)
- Restore default prefork pool with concurrency=8 in worker config
- Add architect queue to worker while keeping main's pool settings
- Remove unused sync completion import from litellm provider

* feat(sdk): centralize Target interface in SDK

Move Target and TargetResponse base classes from penelope to
sdk.targets so both Penelope and Architect can share them without
circular dependencies. Add LocalEndpointTarget for direct backend
service invocation. Penelope's targets.base becomes a re-export shim.

* feat(sdk): implement architect phase 06 conversational UX

Add discovery state tracking, compiled observations, guided discovery
prompts, progress awareness, and entity links in responses. Wire
ExploreEndpointTool in backend worker via target_factory. Propagate
MCP ToolAnnotations (readOnlyHint, destructiveHint) through server
and client for accurate write-guard classification. Replace magic
strings with StrEnum constants (Action, Role, ToolMeta, InternalTool).
Add SmartLink component for internal entity navigation in frontend.

* test(tests): add architect agent tests and fix truncation

Add tests for LocalEndpointTarget, ExploreEndpointTool (bound and
unbound modes), discovery state formatting, SmartLink, and
_make_target_factory. Fix test_result_content_truncation to assert
the actual 4000-char limit instead of the stale 300-char value.

* fix(architect): resolve session scope error and handle file read errors

- Fix `DetachedInstanceError` by saving the session title status before closing the DB session context in `architect_chat_task`
- Wrap `FileReader` operations in `ArchitectChatInput` with try/catch, handle error/abort events, and validate data URL formatting to prevent infinite hangs

* feat(agents): require confirmation for explore_endpoint tool and mandate summary

- Update `requires_confirmation` property on `ExploreEndpointTool` to return `True` to ensure user approval before execution.
- Append a directive to the tool's description instructing the agent to always present a summary of the findings after running the tool.

* fix(architect): persist write-guard state to fix confirmation loop

- Expose `guard_state` property on `ArchitectAgent` to serialize `_needs_confirmation` and `_confirming_tools`
- Update `architect_chat_task` to save and restore `guard_state` from the DB `agent_state` JSON field
- This prevents the agent from forgetting user approvals across turns and getting stuck in a loop where it hallucinates success but never actually executes mutating tools (like `create_project` or `create_behavior`).

* docs(playground): update telemachus README with progress and TODOs

* feat(agents): streamline test execution and conceal nano IDs

- Update system prompt to explicitly restrict printing raw nano IDs in prose.
- Remove complex test configuration management from the agent's workflow; test configurations are now treated as internal backend constructs.
- Add execute_test_set to mcp_tools.yaml and update the agent's system prompt to use this simplified tool for running tests.
- Instruct agent that project creation is optional.
- Update telemachus README with new TODO regarding test execution flow.

* docs(playground): add Phase 11 for advanced multi-turn endpoint exploration

* feat(agents): surface tool internal reasoning to the frontend

- Update AgentEventHandler to accept an optional `reasoning` string on tool start.
- Pass the LLM's reasoning from `AgentAction` down through `_execute_tools` in `BaseAgent`.
- Update PenelopeAgent and TurnExecutor to emit `on_tool_start` and `on_tool_end` callbacks, exposing its internal ReAct loop.
- Use `asyncio.run_coroutine_threadsafe` inside `ExploreEndpointTool` to bridge synchronous Penelope callbacks to the async event loop.
- Update WebSocket handler to include `reasoning` in the `ARCHITECT_TOOL_START` payload.
- Update React hooks and component state to track and store `reasoning` for active and completed tools.
- Conditionally render tool reasoning below tool descriptions in the UI, styled cleanly without hardcoding.
- Update relevant unit tests to reflect async changes and new type signatures.

* chore: general code formatting and minor fixes

- Fix: LocalToolProvider now raises ValueError on tool not found and handles empty request bodies gracefully.
- Feat: Add support for YAML-only parameters in MCP schema builder.
- Feat: Include `attachments_text` in Architect iteration prompt template.
- Refactor: Move ArchitectChat input area into dedicated `ArchitectChatInput` component.
- Style: Run Prettier/ESLint to auto-format various frontend components and tests.

* docs(playground): add migration rebase TODO

* feat: add prompt hardening and permission management

Phase 07 (entity linking): restore file/mention chips on session
reload, add entity-type highlighting in message bubbles.

Phase 08 (test execution): fix test_set_id parameter mismatch,
remove misleading tools, add execution monitoring guidance.

Phase 09 (prompt hardening): add security boundaries section to
system prompt (identity, injection resistance, information
boundaries, tool safety, off-topic). Harden streaming response
prompt. Add structural argument validation with payload, string,
and array size limits.

Phase 10 (permission management): add session-level auto-approve
toggle, plan-level approval (all mutating tools unlocked on
confirm), end-to-end flow from frontend to SDK.

Tests: 14 prompt hardening tests, 9 auto-approve tests,
2 backend handler tests, 1 updated plan-approval test.

* feat(frontend): improve architect streaming indicators UX

Replace identical spinners for thinking/tool states with distinct visuals:
animated dots for thinking, spinning gear icon for active tools, indented
tool list with collapsible reasoning and entrance animations. Auto-focus
chat input on new sessions. Show elapsed time next to tool calls.

* feat(sdk): add server-side tool execution duration tracking

Track wall-clock time for tool calls using time.monotonic() in both the
SDK agent loop and Penelope executor. Propagate duration_ms through
ToolResult to the backend WebSocket event payload. Frontend prefers
server-measured duration, falls back to client-side estimate.

* fix(backend): make architect migration idempotent

Use IF NOT EXISTS / DROP IF EXISTS guards so the migration
can be safely re-run after a rebase without DuplicateTable
errors.

* feat(sdk): add exploration strategies and optimize perf

Introduce a target-agnostic strategy framework for Penelope:
- DomainProbingStrategy, CapabilityMappingStrategy,
  BoundaryDiscoveryStrategy with template-method pattern,
  ACD/AutoRedTeamer-inspired novelty filtering and difficulty
  calibration
- ExploreEndpointTool strategy/comprehensive mode support
- Defer GoalAchievementJudge LLM calls to early-stop-eligible
  turns only (~60% fewer judge calls per strategy)
- Parallelize capability_mapping + boundary_discovery in
  comprehensive mode via asyncio.gather

* feat(sdk): present exploration modes to user

Update Architect system prompt so it asks the user to choose
between Quick (domain probing) and Comprehensive (all three
strategies) before starting exploration. Defaults to Quick
when the user doesn't express a preference.

* fix(sdk): accept duration_ms in on_tool_end callback

The executor passes duration_ms as a third argument to
on_tool_end but the callback in ExploreEndpointTool only
accepted two, causing a silent TypeError that prevented
tool-end events from reaching the frontend.

* fix(frontend): show active tools first, collapse completed

Reorder ToolCallList to render running tools at the top so
the user sees current progress immediately. When tools are
active, all completed tools collapse into the "N completed"
group instead of leaving the last two visible.

* fix(sdk): suppress confirmation UI when auto-approve is on

The LLM's needs_confirmation flag was passed through unchanged
even when auto_approve_all was true, causing Accept/Change
buttons to appear despite the toggle being enabled. Override
needs_confirmation to false in the agent's finish handler when
auto-approve is active, and also check the toggle state in the
frontend as a second safeguard.

* fix(frontend): fix broken entity links in architect chat

Remove link patterns for behaviors and test-results which
have no detail pages (404). Update both system_prompt.j2 and
streaming_response.j2 to instruct the LLM to refer to those
entities by name only. Open internal links in a new tab so
clicking them doesn't navigate away from the chat.

* refactor(sdk): modularize architect agent and enhance plan tracking

Extract configuration, tool registry, and schema generation into
dedicated modules. Add AgentMode enum, ArchitectConfig dataclass,
unified tool category registry, and auto-generated save_plan schema
from Pydantic model. Make project optional, add MappingSpec for
trackable behavior-metric mappings, and update prompts for
reuse-aware execution.

* feat(backend): update mcp tools and wire AgentMode enum

Rename synthesize_tests to generate_test_set in mcp_tools.yaml,
activate job status endpoint, add odata navigation property docs,
and use AgentMode enum when restoring architect session state.

* fix(frontend): fix architect UI and add session state management

Fix empty confirmation bubble by skipping content-less messages and
attaching actions to the last message with content. Add plan
completion indicator with green border and checkmark. Fix plan font
size, input focus on reject, tool list ordering, markdown link
normalization, and task list checkbox styling. Reset mode and plan
on session switch, restore them when loading existing sessions.

* fix(frontend): backfill empty streaming message content

When the agent completes without streaming text chunks (e.g. after
tool execution), the streaming message was finalized with empty
content and then hidden by the filter. Now backfills content from
the response payload so the message is always displayed.

* fix(sdk): enforce plan constraints and fix mapping tracking

- Add ID-to-name resolution so add_behavior_to_metric (which uses
  UUIDs) can match plan mappings and mark them as completed
- Add structural guard rejecting create_project when plan has no
  project and create_metric when name doesn't match the plan
- Update system prompt to use create_metric with exact plan names
  instead of generate_metric which produces its own names
- Update mapping format in prompt to array of MappingSpec objects

* docs: update telemachus implementation status

Mark Phase 11 as done, add Phase 12 (plan-aware execution) and
Phase 13 (architect refactoring) with detailed write-ups. Add
UI/UX improvements section and expand key files table.

* feat(backend): add signal-based async task notification

Replace polling-based task monitoring with event-driven approach
using Celery task_postrun signal and Redis coordination. Adds
test_run_id matching for chord-based test execution, await_task
tool for the architect agent, and plan constraint guards.

* fix(backend): enforce default $select and improve UX

Add default_query support to MCP tools so large fields (response,
evaluation_prompt) are excluded by default. Fix double-confirmation
on execute_test_set, remove stale polling instructions from prompts,
and enforce human-readable names in link text instead of UUIDs.

* fix(backend): rebase architect migration on chunk table head

The merge from origin/main introduced d22819b0aa66 (chunk table) as a
second head alongside c4d8e2f1a3b5 (architect tables), both descending
from e1f2a3b4c5d6. Update the architect migration's down_revision to
d22819b0aa66 so Alembic has a single linear head.

* chore: untrack playground/telemachus/README.md

The file is covered by the playground/* gitignore rule but was
previously committed. Remove from tracking so local changes
no longer show up in git status.

* fix(sdk): merge duplicate [tool.uv.sources] table in pyproject.toml

* feat(backend): add run comparison via stats MCP tools

Expose existing /test_results/stats and /test_runs/stats endpoints
as MCP tools so the Architect can compare test runs by pass rate,
behavior, and metric. Add comparison workflow guidance to the system
prompt and streaming response template.

* fix(backend): rebase architect migration on garak head

* feat(backend): add list_sources tool and knowledge source param

- Add list_sources MCP tool (GET /sources/) with title-based filtering,
  $select, limit/skip pagination, and a 100-item default page size
- Add sources parameter to generate_test_set for grounding single-turn
  test generation in platform knowledge sources (ID-only, backend fetches
  content automatically)
- Fix null YAML parameter handling in tools.py (bare keys normalised to {})
- Refine get_test_result and get_test_result_stats descriptions for
  post-run analysis workflows

* feat(sdk): add knowledge source grounding and result analysis

- Add Knowledge Sources section to system_prompt.j2: ID-only workflow,
  when to use/skip sources, list_sources → generate_test_set flow, and
  hard rules (no content fetching, no fact fabrication, single-turn only)
- Add Result Analysis section to system_prompt.j2: standard analysis
  workflow, failure pattern interpretation, and actionable suggestion types
- Update post-execution workflow to include get_test_result_stats (mode=all)
  and targeted failure drill-down via get_test_result reason field
- Add single-run analysis output structure to streaming_response.j2
- Register list_sources in TOOL_REGISTRY with AgentMode.DISCOVERY
- Pin mcp to 1.26.0 for stable streamable-http support

* feat(frontend): add knowledge source @mention support

- Add source entity type to ENTITY_TYPES in ArchitectChatInput, fetching
  from /sources/ with title-contains filter
- Add source mention colour (error.main) in both ArchitectChatInput and
  ArchitectMessageBubble
- Extend mentionRegex to recognise @source: prefixed mentions

* feat(frontend): add architect logo to welcome screen

* fix(frontend): reset plan state when user sends a new message

* fix(frontend): fix @-mention listing, search, and UI polish

- enable @-mention dropdown on empty query (show all by default)
- strip hint markup from inserted mention text on selection
- add awaiting_task state to show spinner during background jobs
- tighten welcome screen layout and message bubble rendering
- expose awaiting_task field from websocket event types

* feat(backend): add server-managed pagination to MCP tools

Introduce page_size in mcp_tools.yaml to give each list_* tool a
server-controlled page size. The server requests page_size+1 items
(peek-ahead), trims to page_size, and wraps the response in a
_pagination envelope so the LLM always knows whether more results exist.

- add apply_query_overrides and format_list_response helpers to tools.py
  and share them between server.py and local_tools.py
- remove limit from LLM-visible schema for paginated tools so the agent
  cannot override server-managed page sizes
- remove dead override_query mechanism (superseded by page_size)
- downgrade per-call debug logs to logger.debug
- add Pagination section to architect system prompt explaining the
  _pagination envelope and has_more/next_skip usage

* fix(backend): add \$select support to sources and tests endpoints

Without field projection, listing 40+ sources returns full schema
objects (with source_metadata, tags, counts, nested relations) which
overflows the LLM context window and causes truncated results.

Adding \$select (already present on endpoints, behaviors, metrics, etc.)
lets the agent request only the fields it needs, keeping list responses
small regardless of collection size.

* fix(sdk): disable aiohttp transport and expose awaiting_task status

- disable litellm aiohttp transport to prevent 'attached to a different
  loop' errors when running inside Celery worker threads
- expose awaiting_task flag in architect task WebSocket events so the
  frontend can show a spinner while background jobs are pending

* style(frontend): replace hardcoded borderRadius with theme values

* style(sdk): fix E501 line-length violations

* style(sdk): apply ruff formatting to architect and tools modules

* fix(sdk): fix vertex_ai credential security and streaming

* style(backend): apply ruff formatting

* style(penelope): sort imports to fix ruff I001 violations

* fix(sdk): include file path in credential error but suppress base64 values

* fix: address peqy review — security, header propagation, config alignment

- Verify architect session ownership in WebSocket handler before
  persisting messages (was missing org/user check unlike REST route)
- Propagate X-Total-Count header from with_count_header into directly
  returned Response objects (e.g. JSONResponse on $select paths)
- Guard apply_select __dict__ fallback against _sa_instance_state and
  other private SQLAlchemy attrs
- Log MCP secret-key lookup failures at ERROR instead of swallowing them
- Align architect_monitor Redis URL to BROKER_URL || REDIS_URL fallback
- Reduce delegation token default TTL from 60m to 15m; update test

* fix(security): prevent accidental secret leakage in logs

- Remove user message body from INFO logs in chat and architect
  WebSocket handlers (replace with message length only)
- Replace raw str(e) in Redis exception logs with type(e).__name__
  to prevent connection URLs (which may contain passwords) from
  reaching log aggregators
- Harden MCP auth log: use a fixed string instead of interpolating
  the exception, guarding against future HTTPException detail changes

* style(penelope): apply ruff formatting to strategy files

* style(frontend): apply prettier formatting to architect components

* fix(tests): update architect handler tests for session ownership check

- Use valid UUIDs for session_id so UUID() conversion succeeds
- Mock crud.get_architect_session to return a truthy session object
- Add explicit test for unauthorized session rejection
- Also import UUID for use in assertion

* fix(frontend): resolve ESLint errors in architect components

- Use tool.startedAt as stable React key instead of array index in
  ToolCallList (activeTools and completedTools maps)
- Use filename+size as stable key instead of array index in
  ArchitectChatInput file chip list
- Guard targetType nullability instead of non-null assertion (!)
- Prefix unused onSessionTitleUpdate prop with _ in ArchitectChat
- Add startedAt field to completedTools type in StreamingState and
  update all test fixtures accordingly

* fix(frontend): resolve TypeScript type check errors in architect components

- Add $filter to PaginationParams so getEndpoints/getMetrics accept OData filters
- Fix TestRunDetail.name nullable: filter and map to non-optional shape
- Fix Palette type assertion to go via unknown first

* fix(frontend): fix elliptical chat bubble caused by double borderRadius multiplication

Theme functions returning numbers go through MUI sx borderRadius transform
a second time, making values 4x too large. Return px strings from theme
functions to bypass the multiply-by-borderRadius transform.

* style(frontend): apply prettier formatting to architect components, style(auth): update login page badge label (#1663)....

**SDK v0.7.0:**
- Introduces Rhesis Architect, an AI agent for test suite design and execution, including a chat interface with streaming, entity linking, and plan confirmation.
- Adds adaptive testing features with diversity-aware suggestions, async embedding generation, and a unified suggestion pipeline.
- Enables flexible model selection with separate execution and evaluation models, and allows per-request model overrides.
- Improves telemetry with retry logic for transient export failures and enhances security by preventing accidental secret leakage in logs.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.6.12] - 2026-04-09

### Platform Release

This release includes the following component versions:
- **Backend 0.6.11**
- **Frontend 0.6.12**
- **SDK 0.6.12**
- **Polyphemus 0.2.9**

### Summary of Changes

**Backend v0.6.11:**
- **New Feature:** Added core embedding generation services and tasks for vector embeddings, including deduplication and stale embedding cleanup.
- **New Feature:** Implemented automatic source chunking service with soft-delete and re-chunking support.
- **Improvement:** Replaced Celery chord fan-out with an async batch execution engine for faster test runs and added a cancel test run endpoint.
- **Improvement:** Enhanced adaptive testing with streaming suggestions, UI improvements, and the ability to export to regular test sets.


**Frontend v0.6.12:**
- Implemented asynchronous batch execution engine for tests, replacing chord fan-out, improving performance and adding test run cancellation.
- Added "echo" use case to chatbot, returning user input verbatim without LLM calls or rate limit consumption.
- Introduced adaptive testing features including streaming suggestions, batch accept, segmented progress bar, export to regular test sets, user feedback, per-metric evaluation details, and settings management.
- Improved file import functionality with fixes for XLSX parsing, support for multi-turn turn configuration, and test-type mismatch warnings.
- Enhanced performance through thread-local clients for HTTP and RPC connections, reduced object construction, and mop-up pass for retrying transient failures.
- Added cancel test run endpoint and UI, allowing users to cancel in-progress test runs.


**SDK v0.6.12:**
- feat: Added lightweight `rhesis-telemetry` package for telemetry foundation.
- feat: Implemented async batch execution engine for tests, improving concurrency and performance.
- feat: Added "echo" chatbot use case that returns user input verbatim without LLM calls.
- feat: Introduced test run cancellation functionality with UI and backend support.
- perf: Optimized batch execution performance by reusing thread-local clients and reducing object construction.
- fix: Implemented lazy loading for metrics, services, and models to improve SDK startup time.
- feat: Added user feedback functionality for adaptive testing suggestion generation.


**Polyphemus v0.2.9:**
- Removed PyTorch dependency, reducing Docker image size.
- Implemented NIST-aligned password hardening with increased minimum length and breach checks.
- Fixed issues with test run metrics filtering and display in the frontend.
- Add attachments column to tests grid.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.6.11] - 2026-03-26

### Platform Release

This release includes the following component versions:
- **Backend 0.6.10**
- **Frontend 0.6.11**
- **SDK 0.6.11**

### Summary of Changes

**Backend v0.6.10:**
- Added trace metrics evaluation system with per-turn and per-conversation metric evaluation via Celery tasks.
- Added trace review system with human review overrides for traces, turns, and individual metrics.
- Added SQL-level trace metrics aggregation for improved performance over Python-side processing.
- Added Trace scope to MetricScope, enabling metrics to target traces alongside test results.
- Added configurable debounce for conversation-level metric evaluation.
- Introduced ReviewTarget enum for type-safe review target constants across the codebase.
- Added task and comment support for traces.
- Improved operational safety: sanitized API error messages, added Celery task time limits, and refined retry strategy for transient errors.

**Frontend v0.6.11:**
- Added trace metrics tab with detailed per-metric breakdown, status indicators, and metric-level reviews.
- Added trace reviews tab with per-turn and per-metric human review overrides.
- Added trace review drawer for submitting reviews with target selection and status toggles.
- Added project-level trace metrics configuration with bulk selection and removal.
- Added evaluation status filter to the traces list with pass/fail/pending filtering.
- Added dedicated trace detail page at `/traces/[identifier]`.
- Improved trace filters with theme-aware styling replacing hardcoded colors.
- Added error boundary around trace drawer content for improved resilience.
- Memoized span attribute categorization for better render performance.

**SDK v0.6.11:**
- Replaced custom chunking logic with `chonkie`-backed strategies (TokenChunker, SentenceChunker, RecursiveChunker), improving text splitting capabilities. Deprecated the custom SemanticChunker.
- Fixed a security vulnerability by pinning the `litellm` dependency to version <=1.82.3 due to compromised newer versions.
- Improved connector stability by making test and metric executions non-blocking, preventing connection drops during concurrent runs.
- Removed strict input validation from base judge to support conversational trace metrics evaluation.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)

## [0.6.10] - 2026-03-23

### Platform Release

This release includes the following component versions:
- **Backend 0.6.9**
- **Frontend 0.6.10**
- **SDK 0.6.10**

### Summary of Changes

**Backend v0.6.9:**
- Added API endpoint to delete adaptive testing test sets.
- Added SDK stats API for test runs and test results.
- Exposed test execution context in request mapping templates.
- Improved backend performance with DB views, indexes, and cleanup.
- Implemented NIST-aligned password hardening with breach checks.
- Added overwrite functionality for test generation and evaluation in adaptive testing.
- Refactored metric configuration handling and evaluation.
- Migrated feedback and polyphemus emails to backend email service.
- Added evaluate endpoint and UI for adaptive testing.
- Fixed welcome email not sent on email/password and magic link sign-up.
- Added attachments column to tests grid.
- Fixed counts including soft-deleted records.
- Fixed MCP auth: use system default model and fix credential testing.
- Bumped security deps (tornado, langgraph, mcp-atlassian).


**Frontend v0.6.10:**
- Redesigned login and registration pages with a new white-dominant theme and improved accessibility.
- Added the ability to delete adaptive testing test sets.
- Implemented overwrite functionality for test generation and evaluation in adaptive testing.
- Improved test run detail page search functionality and fixed pagination issues.
- Added an Attachments column to the Tests grid, displaying the number of attached files.


**SDK v0.6.10:**
- Added `TestRuns.stats()` and `TestResults.stats()` methods for retrieving test run and result statistics, including optional pandas DataFrame conversion.
- Implemented NIST-aligned password hardening with zxcvbn strength scoring, context-specific word blocking, and HaveIBeenPwned breach checks. Minimum password length increased to 12 characters.
- Improved metric evaluation by refactoring the MetricEvaluator to use a strategy pattern, allowing for more flexible backend integrations and streamlined configuration handling.
- Made SDK metrics evaluation async-first, enhancing performance with asynchronous execution methods in judges and metrics.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.6.9] - 2026-03-12

### Platform Release

This release includes the following component versions:
- **Backend 0.6.8**
- **Frontend 0.6.9**
- **SDK 0.6.9**
- **Polyphemus 0.2.8**

### Summary of Changes

**Backend v0.6.8:**
- Adds multi-target review annotations for test runs, allowing reviews of turns, metrics, and test results with override logic to mutate test data based on review verdicts.
- Introduces SDK-side metric evaluation via a new `@metric` decorator and connector protocol, enabling client-side metric execution and integration with the backend.
- Enhances conversation evaluation with per-turn metadata, context, and tool_calls, providing richer information for conversational metrics and judges.
- Refactors backend logging to use the standard Python `logging` library, improving maintainability and configurability.


**Frontend v0.6.9:**
- Adds multi-target review annotations, including @mention support in review comments, resizable split panels, and review overrides reflected in test results.
- Enhances conversation evaluation with per-turn metadata, context, and tool_calls, displayed in the conversation history.
- Improves project management with pagination, search, and filters in the projects list, along with disambiguation of duplicate project names.
- Upgrades dependencies to address security vulnerabilities and adds comprehensive E2E test coverage for all overview and detail pages.


**SDK v0.6.9:**
- Fix: Resolved issues with the Polyphemus provider, including bad requests and updated default model name.
- Feature: Upgraded Garak to v0.14 with dynamic probe generation, centralized detector registry, and code quality improvements.
- Feature: Implemented async-first model generation for improved performance, including updates to LiteLLM, RhesisLLM, and VertexAILLM providers.
- Feature: Added per-turn metadata, context (RAG sources), and tool_calls to conversation evaluation, enhancing conversational metrics and providing more detailed information in the UI.
- Feature: Implemented batch processing and retry mechanisms in the synthesizer for more efficient test set generation.
- Fix: Resolved multiple security vulnerabilities by upgrading dependencies and adding npm overrides.


**Polyphemus v0.2.8:**
- Upgraded to Python 3.12 with corresponding dependency updates and conflict resolution.
- Added `generate_batch` endpoint for handling multiple requests.
- Implemented rolling model replacement for Vertex AI deployments to ensure zero-downtime updates.
- Resolved multiple security vulnerabilities in dependencies.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.6.8] - 2026-03-05

### Platform Release

This release includes the following component versions:
- **Backend 0.6.7**
- **Frontend 0.6.8**
- **SDK 0.6.8**

### Summary of Changes

**Backend v0.6.7:**
- Added multi-file attachment support for tests, traces, and playground, including file upload/download, format filters, and UI elements.
- Enhanced chatbot functionality with file upload support and JSON output mode.
- Improved test run detail view with metadata, file sections, and trace drawer integration.
- Added LiteLLM Proxy, Azure AI, and Azure OpenAI provider support.


**Frontend v0.6.8:**
- Added support for file attachments to tests, test results, and chat functionality, including UI elements for upload, download, and display.
- Enhanced test run detail view with metadata, context, pretty-printed JSON, file attachments, and navigation improvements.
- Introduced LiteLLM Proxy, Azure AI, and Azure OpenAI provider support with optional API base and version configurations.
- Improved test coverage with new unit, integration, E2E, and accessibility tests, along with fixes for various bugs and UI issues.


**SDK v0.6.8:**
- Added multi-file attachment support for tests, traces, and playground, including file upload, download, and display in the UI.
- Added Azure AI Studio and Azure OpenAI providers.
- Added `connect()` blocking API for connector-only scripts.
- Enhanced SDK model factory with registry-driven creation for easier provider management.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.6.7] - 2026-03-02

### Platform Release

This release includes the following component versions:
- **Backend 0.6.6**
- **Frontend 0.6.7**
- **SDK 0.6.7**
- **Polyphemus 0.2.7**

### Summary of Changes

**Backend v0.6.6:**
- Added explicit `min_turns` parameter to test configuration, allowing control over early stopping behavior.
- Improved turn budget handling in Penelope, including turn-aware prompts and deepening strategies, and preventing premature stopping.
- Enhanced metric handling, including pagination on the frontend and passing `conversation_history` to conversational metrics.
- Added methods to TestSet for bulk association/disassociation of tests.


**Frontend v0.6.7:**
- Enhanced multi-turn evaluation with accurate turn counting (user-assistant pairs), `min_turns`/`max_turns` configuration, and SDK improvements for metric handling.
- Added explicit `min_turns` parameter for early stop control in conversational tests, configurable through a range slider in the frontend.
- Improved metric handling in the SDK with create-or-update support, ID preservation, and fixes for null value overwrites.
- Added methods to associate/disassociate tests with TestSets without recreating them.
- Fixed metrics page pagination to display all backend type tabs.


**SDK v0.6.7:**
- Added explicit `min_turns` parameter to control early stopping in tests, replacing instruction-based regex parsing.
- Improved turn budget handling in Penelope, including turn-aware prompts, explicit min/max turn labeling, and preventing spurious turn count criteria in goal judging.
- Enhanced metric handling in the SDK, including create-or-update support for metric push, preservation of IDs on pull, and fixes for conversational metric evaluation.
- Added methods to TestSet for bulk association/disassociation of tests, improving test set management.


**Polyphemus v0.2.7:**
Initial release or no significant changes.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.6.6] - 2026-02-26

### Platform Release

This release includes the following component versions:
- **Backend 0.6.5**
- **Frontend 0.6.6**
- **SDK 0.6.6**
- **Polyphemus 0.2.6**

### Summary of Changes

**Backend v0.6.5:**
- Security: Mitigated OAuth callback URL host header poisoning vulnerability. Addressed multiple Dependabot security alerts by updating vulnerable dependencies (cryptography, pillow, fastmcp, redis, langgraph-checkpoint, marshmallow, virtualenv, mammoth, langchain-core).
- Polyphemus Integration: Added core Polyphemus integration including service delegation tokens, access control system with request/grant workflow, and frontend UI for access requests.
- Tracing: Implemented conversation-based tracing across SDK, backend, and frontend, enabling the linking of multi-turn conversation interactions under a shared trace_id. Added UI improvements for conversation traces, including turn navigation, edge labels, and resizable trace detail drawer.
- Test Set Type Enforcement: Enforced the requirement of `test_set_type` on test set creation across the backend, frontend, and SDK, and enforced type-matching when assigning tests to test sets.


**Frontend v0.6.6:**
- Added Polyphemus access request UI, including access request modal, model card UI states, and Polyphemus provider icon/logo.
- Improved trace UI with conversation tracing support, including conversation icon in trace list, type filter buttons, Conversation View tab, turn labels, and turn navigation.
- Enhanced trace graph view with turn labels on edges, progressive agent invocation count, and improved edge routing.
- Fixed security vulnerabilities in frontend transitive dependencies.


**SDK v0.6.6:**
- Enhanced Polyphemus integration with access control, delegation tokens, and UI.
- Improved LLM error handling with retries, logging, and fallback mechanisms.
- Added conversation-based tracing across SDK, backend, and frontend for multi-turn interactions.
- Addressed multiple security vulnerabilities by updating dependencies and migrating to PyJWT.


**Polyphemus v0.2.6:**
- Added rate limiting to the Polyphemus service.
- Implemented access control and delegation tokens for Polyphemus authentication, including a request/grant workflow and frontend UI.
- Deployed vLLM to Vertex AI for Polyphemus, including caching GCP credentials and adding retry logic.
- Resolved multiple security vulnerabilities by updating dependencies, including migrating from python-jose to PyJWT.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.6.5] - 2026-02-18

### Platform Release

This release includes the following component versions:
- **Backend 0.6.4**
- **Frontend 0.6.5**
- **SDK 0.6.5**

### Summary of Changes

**Backend v0.6.4:**
Key changes include: Evaluate three-tier metrics during live multi-turn execution (#1366)

* feat: evaluate three-tier metrics during live multi-turn execution

Previously, only Penelope's Goal Achievement metric was evaluated during
live multi-turn test execution. Additional metrics defined in the
three-tier model (behavior > test set > execution) were ignored.

Backend: add exclude_class_names to evaluate_multi_turn_metrics() and
call it after Penelope's evaluation to pick up additional metrics.
Frontend: show metrics table for multi-turn tests with additional
metrics and use all metrics for pass/fail determination.

* fix(test): update multi-turn runner tests for additional metrics evaluation

Update test expectations to reflect that evaluate_multi_turn_metrics is
now called during live execution to pick up additional three-tier
metrics. Add test for merging additional metrics with Penelope results., Add AI-powered auto-configure for endpoint mappings (#1364)

* feat(backend): add auto-configure endpoint service

Add AI-powered auto-configuration that analyzes user-provided reference
material (curl commands, code snippets, API docs) and generates Rhesis
request/response mappings. Includes LLM-driven analysis, endpoint
probing with self-correction, and comprehensive prompt engineering for
conversation mode detection and platform variable mapping.

* feat(frontend): add auto-configure modal and UI

Add AutoConfigureModal with two-step stepper (input + review), integrate
auto-configure button in endpoint creation form, move auth token to
basic info tab, and fix project-context redirect after creation.

* fix(frontend): fix redirect after endpoint creation

Remove /endpoints suffix from project-context redirect so it navigates
to the project detail page instead of a non-existent route.

* feat(sdk): add auto_configure class method to Endpoint

Add Endpoint.auto_configure() for code-first auto-configuration using
the backend service, with probe control and result inspection.

* docs: update endpoint docs for auto-configure and platform variables

Add auto-configure documentation page. Update platform variable tables
to include all managed fields (conversation_id, context, metadata,
tool_calls, system_prompt). Fix conversation_id scope to cover all
conversational endpoints, not just stateful. Add response mappings for
tool_calls and metadata in provider examples.

* refactor(backend): restructure auto-configure prompts with endpoint taxonomy

Rewrite both auto_configure.jinja2 and auto_configure_correct.jinja2
around a clear hierarchical taxonomy: single-turn vs multi-turn
(stateless | stateful). This replaces the previous flat three-category
approach with a two-step classification that improves LLM accuracy.

* feat(backend): add API key detection and redaction for auto-configure

Prevent real API keys from being sent to the LLM during auto-configure.
Backend redacts secrets (OpenAI, AWS, Google, Bearer tokens) before
prompt rendering. Frontend shows a warning and blocks submission when
keys are detected. Environment variable placeholders are preserved.

* chore: update chatbot uv.lock

* style(frontend): use theme borderRadius in AutoConfigureModal

* fix(frontend): resolve ambiguous label queries in auto-configure tests

Use getByRole('textbox') instead of getByLabelText to avoid matching
the Tooltip aria-label on the disabled Auto-configure button. Also
prefix unused FAILED_RESULT fixture with _ to fix eslint warning.

* ci: ignore empty uv cache in sdk test workflow

The uv cache clean step wipes the cache directory, causing the
post-job save to fail. Add ignore-nothing-to-cache to prevent this.

* fix(frontend): resolve test timeouts in auto-configure tests

Use userEvent.setup({ delay: null }) to remove inter-keystroke delays
that caused CI timeout exceeding the 5s limit.

* fix: resolve lint errors and test timeouts

* chore: formatting and lint fixes

* fix(backend): resolve UnmappedClassError in tests

* fix: address PR #1364 review comments

- Update schema: request_mapping and response_mapping now support nested JSON (Dict[str, Any])
- Add SSRF protection: block cloud metadata services (169.254.0.0/16) while allowing localhost
- Fix auth token substitution: support custom headers like x-api-key, not just Authorization
- Update LLM prompts: clarify nested JSON support and warn against mapping $.id to conversation_id
- Improve UX: remove auth_token requirement for auto-configure (support open APIs)
- Fix: pre-existing TypeScript error in BehaviorsClient.tsx

Addresses all 5 issues raised by @peqy in PR review.....

**Frontend v0.6.5:**
Key changes include: Evaluate three-tier metrics during live multi-turn execution (#1366)

* feat: evaluate three-tier metrics during live multi-turn execution

Previously, only Penelope's Goal Achievement metric was evaluated during
live multi-turn test execution. Additional metrics defined in the
three-tier model (behavior > test set > execution) were ignored.

Backend: add exclude_class_names to evaluate_multi_turn_metrics() and
call it after Penelope's evaluation to pick up additional metrics.
Frontend: show metrics table for multi-turn tests with additional
metrics and use all metrics for pass/fail determination.

* fix(test): update multi-turn runner tests for additional metrics evaluation

Update test expectations to reflect that evaluate_multi_turn_metrics is
now called during live execution to pick up additional three-tier
metrics. Add test for merging additional metrics with Penelope results., Fix e2e projects content test selectors (#1365)

* fix(e2e): fix projects content test selectors

Add networkidle wait, use .MuiCard-root instead of [class*="ProjectCard"],
and broaden create button detection to include link role.

* fix(e2e): use resilient selectors in projects content test

Restore broader /create|new/i regex for create button matching and
replace generic main element fallback with projects-specific heading.....

**SDK v0.6.5:**
- Added AI-powered auto-configuration for endpoints, simplifying setup with intelligent analysis and probing.
- Introduced Adaptive Testing features, including a Test Explorer UI, CRUD operations for tests and topics, and output generation capabilities.
- Unified model handling with a single `get_model()` function, simplifying model selection and configuration.
- Improved performance and concurrency in output generation using asynchronous HTTP requests.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.6.4] - 2026-02-12

### Platform Release

This release includes the following component versions:
- **Backend 0.6.3**
- **Frontend 0.6.4**
- **SDK 0.6.4**
- **Polyphemus 0.2.5**

### Video Overview

Watch the overview of this release:
- Metrics per Run + Output re-runs: https://youtu.be/vdbWfqhQpZs
- Multi-Agent Workflow Testing & Observability: https://youtu.be/OH7e_7q7_oU

### Summary of Changes

**Backend v0.6.3:**
- Added split-view playground with test creation from conversations.
- Implemented file import for test sets with support for CSV, JSON, JSONL, and Excel formats.
- Enhanced test set execution with rescoring, last run retrieval, and metric management.
- Introduced user-configurable embedding model settings and connection testing.
- Replaced Auth0 with a native authentication system including email verification, password reset, and magic link.


**Frontend v0.6.4:**
- Added split-view playground with test creation from conversations, including a drawer with LLM-extracted pre-filled fields for both single-turn and multi-turn tests.
- Implemented file import for test sets, supporting CSV, JSON, JSONL, and Excel formats with column mapping and user-friendly error handling.
- Added user-configurable embedding model settings, allowing users to select their preferred embedding model and test the connection.
- Introduced test output reuse and re-scoring capabilities, enabling users to re-evaluate metrics on stored outputs without invoking endpoints, and added a "Scoring Target" dropdown to execution drawers.
- Replaced Auth0 with a native authentication system, including email verification, password reset, magic link, and OAuth support, and added refresh token rotation for improved security.


**SDK v0.6.4:**
- Introduces a split-view playground with test creation from conversations, including file import for test sets and flat convenience fields for multi-turn test configurations.
- Adds rescore, last_run, and metric management capabilities to TestSet, along with user-configurable embedding model settings and improved model connection testing.
- Implements a native authentication system replacing Auth0, featuring email verification, password reset, magic link login, and refresh token rotation.
- Improves error messages for model configuration and worker availability, providing clearer guidance for users to resolve issues.


**Polyphemus v0.2.5:**
- Enabled BetterTransformer optimization in Polyphemus, resulting in a 1.5-2x inference speedup.
- Improved error messages for model configuration and worker availability issues, providing users with clear guidance on how to resolve them.
- Enhanced model connection testing, validating model configurations with actual API calls and displaying specific error messages in the UI.
- Updated dependencies to address security vulnerabilities (CVEs) in packages like cryptography, nbconvert, langsmith, protobuf, python-multipart, and others.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.6.3] - 2026-02-05

### Platform Release

This release includes the following component versions:
- **Backend 0.6.2**
- **Frontend 0.6.3**
- **SDK 0.6.3**

### Summary of Changes

**Backend v0.6.2:**
- Added interactive "Playground" for testing endpoints with real-time WebSocket communication, including trace linking and message copy functionality.
- Implemented Jira ticket creation directly from tasks via MCP, with optional Jira space selection during tool connection setup.
- Enhanced WebSocket retry mechanism for improved robustness, including increased reconnect attempts and visibility detection.
- Added creation dates to tests and test sets in the frontend.


**Frontend v0.6.3:**
- feat: Added interactive playground for testing conversational endpoints with real-time WebSocket communication and trace linking.
- feat: Added Jira ticket creation from tasks via MCP integration.
- feat: Enhanced trace visualization with a new Graph View and improved agent tracing, including I/O capture and handoffs.
- feat: Added a `./rh dev` command for simplified local development setup.
- fix: Improved UI/UX with various fixes, including validation improvements and dark mode adjustments.


**SDK v0.6.3:**
- Adds a new interactive playground for testing conversational endpoints with real-time WebSocket communication, including trace viewing and endpoint pre-selection.
- Enhances trace visualization with a new Graph View, agent tracing support, and improved token extraction.
- Introduces JSON and JSONL import/export methods for TestSets.
- Improves WebSocket robustness with enhanced retry mechanism and fixes several SDK test issues.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.6.0] - 2026-01-29

### Platform Release

This release includes the following component versions:
- **Backend 0.6.1**
- **Frontend 0.6.2**
- **SDK 0.6.2**

### Summary of Changes

**Backend v0.6.1:**
- Added Garak LLM vulnerability scanner integration with Redis caching for probe enumeration.
- Implemented 3-level metrics hierarchy for test execution allowing execution-time metric overrides.
- Added MCP Jira/Confluence (Atlassian Stdio), GitHub repository retrieval, and observability integrations.
- Upgraded FastAPI/Starlette, security dependencies, and optimized Docker image with CPU-only PyTorch.

**Frontend v0.6.2:**
- Added 3-level metrics hierarchy UI for test execution with metric source selection.
- Integrated Garak LLM vulnerability scanner import UI for test sets.
- Added MCP Atlassian, GitHub, and observability support in the UI.
- Added context and expected response fields to test run detail view.

**SDK v0.6.2:**
- Added Model entity with provider auto-resolution and Project entity with integration tests.
- Implemented batch processing, embedders framework, and Vertex AI support.
- Added Garak detector metric integration and MCP observability with OpenTelemetry tracing.
- Implemented continuous slow retry mode for connector resilience.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.5.5] - 2026-01-15

### Platform Release

This release includes the following component versions:
- **Backend 0.6.0**
- **Frontend 0.6.0**
- **SDK 0.6.0**
- **Polyphemus 0.2.4**

### Summary of Changes

**Backend v0.6.0:**
- Enhanced connectivity with MCP (Multi Cloud Provider) including Github support and multi-transport capabilities.
- Improved observability with comprehensive OpenTelemetry integration for tracing, visualization, and filtering.
- Chatbot intent recognition added.
- Streamlined organization onboarding with integrated test execution.


**Frontend v0.6.0:**
- Enhanced SDK tracing with improved visualization and filtering in the UI.
- Improved MCP connection stability and added a new GitHub MCP provider.
- Integrated test execution into the organization onboarding process.


**SDK v0.6.0:**
- Added dependency injection support with `bind` parameter in endpoint decorators.
- Enhanced SDK tracing with async support, smart serialization, and improved I/O display.
- Introduced OpenTelemetry integration for basic telemetry.
- Added Chatbot Intent Recognition functionality.


**Polyphemus v0.2.4:**
- Added `bind` parameter to endpoint decorator for dependency injection.
- Introduced Bucket Model for improved data management.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.5.4] - 2025-12-18

### Platform Release

This release includes the following component versions:
- **Backend 0.5.4**
- **Frontend 0.5.4**
- **SDK 0.5.2**
- **Polyphemus 0.2.3**

### Summary of Changes

**Backend v0.5.4:**
- Added a new Polyphemus provider.
- Polyphemus provider now supports schema definitions.


**Frontend v0.5.4:**
- Added new Polyphemus provider with schema support.
- Documentation improvements including guides and SDK metrics.
- Dependency updates for Next.js and Nodemailer.


**SDK v0.5.2:**
- Added a new Polyphemus provider with schema support.
- Improved MCP (likely referring to a component within the SDK) error handling and usability.
- Enhanced metric creation with support for categories and threshold operators.
- Improved generation prompts using research-backed techniques.


**Polyphemus v0.2.3:**
Initial release or no significant changes.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.5.3] - 2025-12-11

### Platform Release

This release includes the following component versions:
- **Backend 0.5.3**
- **Frontend 0.5.3**
- **Polyphemus 0.2.2**

### Summary of Changes

**Backend v0.5.3:**
- Improved MCP authentication and error handling, enhancing usability.
- Added unique constraint to `nano_id` columns in the database.
- Enhanced testing capabilities with endpoint connection testing and multi-turn test support.
- Notifications now separate execution status from test results in emails.


**Frontend v0.5.3:**
- Improved trial drawer with multi-turn support and UX enhancements.
- Added multi-turn test support in manual test writer.
- Fixed authentication errors and improved UX for MCP (Model Comparison Platform).
- Resolved cursor focus loss in title and description fields.


**Polyphemus v0.2.2:**
- Fix: Rate limiting now occurs after authentication, preventing unintended rate limits on unauthenticated requests.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.5.2] - 2025-12-08

### Platform Release

This release includes the following component versions:
- **Backend 0.5.2**
- **Frontend 0.5.2**

### Summary of Changes

**Backend v0.5.2:**
- Added a Test Connection Tool for easier configuration and troubleshooting.
- Removed permission restrictions from entity routes.
- Fixed: Activities API response now returns valid fields.


**Frontend v0.5.2:**
- Security: Updated React and Next.js to address CVE-2025-55182.
- Test Runs: Added support for tags.
- Metrics: Added support for categories and threshold operators.
- Added Test Connection Tool.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)



## [0.5.1] - 2025-12-04

### Platform Release

This release includes the following component versions:
- **Backend 0.5.1**
- **Frontend 0.5.1**
- **Polyphemus 0.2.1**

### Summary of Changes

**Backend v0.5.1:**
- Modernized dashboard with MUI X charts and activity timeline.
- Improved connector output mapping with message field support.
- Added support for OpenRouter provider.
- Increased exporter timeout from 10 to 30 seconds.


**Frontend v0.5.1:**
- Modernized dashboard with MUI X charts and activity timeline.
- Improved MCP import and tool selector dialogs.
- Added grid state persistence to localStorage.
- Backend execution RPC fixes and UI improvements.


**Polyphemus v0.2.1:**
- Added "Is Verified" status to user profiles.
- Users can now be marked as verified.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.5.0] - 2025-11-27

### Platform Release

This release includes the following component versions:
- **Backend 0.5.0**
- **Frontend 0.5.0**
- **SDK 0.5.0**
- **Polyphemus 0.2.0**

### Summary of Changes

**Backend v0.5.0:**
- Added support for multi-turn conversations, including preview, generation, and testing.
- Implemented tool configuration frontend and database persistence for onboarding progress.
- Introduced bidirectional SDK connector with intelligent auto-mapping and in-place test execution.
- Improved test generation and fixed various bugs related to test creation, listing, and format.


**Frontend v0.5.0:**
- Redesigned test results and knowledge detail pages with improved filters and UX.
- Implemented client-side search filter for test results and improved behavior-metrics relation UI.
- Introduced interactive onboarding tour and multi-turn conversation preview in test generation.
- Added tool configuration frontend, tool source type, and bidirectional SDK connector.


**SDK v0.5.0:**
- Added bidirectional SDK connector with intelligent auto-mapping.
- Improved multi-turn test support, including format fixes and comprehensive functionality.
- Enhanced synthesizers and model listing for providers.
- Introduced database functionality for MCP Tool.


**Polyphemus v0.2.0:**
- Added authentication and Google Cloud deployment support.
- Implemented a new benchmarking framework with improved model handling and integration with SDK modules.
- Introduced new metrics including cost heuristic, context retention, and refusal detection; also added summaries and reports.
- Improved judge model memory management and optimized file access.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)



## [0.4.3] - 2025-11-17

### Platform Release

This release includes the following component versions:
- **Backend 0.4.3**
- **Frontend 0.4.3**
- **SDK 0.4.2**

### Summary of Changes

**Backend v0.4.3:**
- Added centralized conversation tracking for improved multi-turn conversation handling.


**Frontend v0.4.3:**
- Fixes a bug that caused the frontend Docker image to fail during local deployment.
- Resolves a file ownership issue (chown bug).


**SDK v0.4.2:**
Initial release or no significant changes.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.4.2] - 2025-11-13

### Platform Release

This release includes the following component versions:
- **Backend 0.4.2**
- **Frontend 0.4.2**
- **SDK 0.4.1**

### Summary of Changes

**Backend v0.4.2:**
- Added support for multi-turn tests, including configuration, execution, and conversational metrics.
- Improved local development setup with Docker Compose and enhanced command-line interface.
- Introduced generic MCP (Multi-Choice Prompting) integration endpoints and user model configuration.
- Added scenarios, tags and comments infrastructure for sources, and improved test set type handling.


**Frontend v0.4.2:**
- Implemented multi-turn test support with configuration UI, goal display, and metrics integration.
- Simplified MCP import workflow to a single-step process with Notion integration in the knowledge page.
- Enhanced test set management with test type display and filtering.
- Improved local development setup with Docker Compose and auto-login feature.


**SDK v0.4.1:**
- Added support for Langchain integration and Penelope language model.
- Introduced Conversational Metrics infrastructure with Goal Achievement Judge and DeepEval integration.
- Enhanced Multi-Chain Processing (MCP) Agent with autonomous ReAct loop, improved error handling, and provider configuration.
- Added structured output support for tool calling via Pydantic schemas and improved VertexAI provider reliability.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.4.1] - 2025-10-30

### Platform Release

This release includes the following component versions:
- **Backend 0.4.1**
- **Frontend 0.4.1**
- **SDK 0.4.0**

### Summary of Changes

**Backend v0.4.1:**
- Added comprehensive OpenTelemetry telemetry system for enhanced monitoring and analytics.
- Enhanced test generation with iteration context support and replaced document uploads with source IDs for improved source tracking.
- Integrated SDK metrics, simplified metric evaluation, and migrated database to SDK format for improved metric handling.
- Introduced soft deletion and cascade-aware restoration for entities, enhancing data management and recovery capabilities.


**Frontend v0.4.1:**
- Enhanced test generation with improved UI, backend support, and source context display. Replaced "Documents" terminology with "Sources" throughout the application.
- Implemented OpenTelemetry for enhanced monitoring and improved telemetry data handling.
- Added support for additional file formats (.pptx, .xlsx, .html, .htm, .zip) for knowledge source uploads with drag-and-drop functionality.
- Improved the display of test results, including error status icons, execution time for failed runs, and quick search functionality in the test runs grid.


**SDK v0.4.0:**
- Added Cohere and Vertex AI LLM providers, and Ollama integration.
- Enhanced AI-based test generation with iteration context support and source ID tracking.
- Improved metrics integration with Ragas and DeepEval, including updated DeepEval to v3.6.7 and new metrics.
- Refactored and improved error handling and schema support for LLM providers, including OpenAI-wrapped schemas.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.4.0] - 2025-10-16

### Platform Release

This release includes the following component versions:
- **Backend 0.4.0**
- **Frontend 0.4.0**
- **SDK 0.3.1**

### Summary of Changes

**Backend v0.4.0:**
- Added support for user-defined LLM providers and model configuration, including metric-specific models and a dedicated model connection test service.
- Implemented soft delete functionality for users and organizations, including recycle bin management and GDPR user anonymization.
- Enhanced source handling with dynamic source types, hybrid cloud/local storage, and improved document extraction.
- Added user settings API endpoints for managing default models and other user-specific configurations.


**Frontend v0.4.0:**
- Enhanced Knowledge section with source upload functionality, improved source preview, and OData filtering for sources grid.
- Redesigned Test Runs detail page with a modern dashboard interface, comprehensive comparison view, and human review integration.
- Improved Models (formerly LLM Providers) management with a new edit modal, connection testing, and API key visibility toggle.
- Added advanced filtering for test results and improved overall UI consistency by using theme values and standardizing styling across components.


**SDK v0.3.1:**
- Added support for user-defined LLM provider generation and execution.
- Enhanced DocumentExtractor with BytesIO support.
- Added `model` parameter support to synthesizer factory and updated ParaphrasingSynthesizer.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.3.0] - 2025-10-02

### Platform Release

This release includes the following component versions:
- **Backend 0.3.0**
- **Frontend 0.3.0**
- **SDK 0.3.0**

### Summary of Changes

**Backend v0.3.0:**
- Added persistent storage for documents with new `StorageService` and updated document endpoints.
- Implemented robust organization-level data isolation and access control across all entities and CRUD operations.
- Enhanced comment and task management features, including email notifications and improved comment counting.
- Introduced a new endpoint for generating test configurations.


**Frontend v0.3.0:**
- **Complete rebranding initiative**: Introduced new Rhesis AI brand identity with updated color palette, logos, and visual design system.
- Implemented comprehensive frontend testing infrastructure.
- Enhanced task management features, including editable task titles, improved UI consistency, and navigation improvements.
- Improved UI/UX across various components, including dashboards, metrics pages, and data grids, with a focus on theme consistency and error handling.


**SDK v0.3.0:**
- Added functionality to push and pull metrics, including categorical and numeric prompt metrics.
- Introduced configuration options for metrics, including enum support and backend configuration.
- Refactored metric classes for improved structure and reusability.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.2.4] - 2025-09-18

### Platform Release

This release includes the following component versions:
- **Backend 0.2.4**
- **Frontend 0.2.4**
- **SDK 0.2.4**

### Summary of Changes

**Backend v0.2.4:**
- Added task management functionality with statuses, priorities, assignments, and email notifications.
- Integrated DocumentSynthesizer for automated document-based test generation.
- Enhanced test set attributes with document sources and metadata tracking.
- Improved database session handling and refactored routes for better performance and maintainability.


**Frontend v0.2.4:**
- Added "Source Documents" section to individual test detail and Test Set Details pages.
- Test sets now display document name and description.
- Project title/description updates without requiring a page reload.
- Added a send button to the comment text box.


**SDK v0.2.4:**
- Rewritten benchmarking framework to integrate SDK modules and improve model handling.
- Introduced `Document` dataclass and `DocumentSynthesizer` for document text extraction and chunking, replacing dictionary-based document handling.
- Added new LLM providers (including Ollama) and improved error handling.
- Refactored metrics, including prompt metrics, and moved them from the backend to the SDK.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.2.3] - 2025-09-04

### Platform Release

This release includes the following component versions:
- **Backend 0.2.3**
- **Frontend 0.2.3**
- **SDK 0.2.3**

### Summary of Changes

**Backend v0.2.3:**
- Added test run stats endpoint with performance improvements.
- Implemented comment support with CRUD operations, API endpoints, and emoji reactions.
- Introduced LLM service integration with schema support and provider modes.
- Improved environment variable handling for local development and deployment flexibility.


**Frontend v0.2.3:**
- Added comments feature for collaboration on tests, test sets, and test runs.
- Improved metrics creation and editing workflow with visual feedback, loading states, and optimized API calls.
- Enhanced test run details with dynamic charts and a test run stats endpoint.
- Fixed tooltip visibility issues and improved performance of the test run datagrid.


**SDK v0.2.3:**
- Renamed and reorganized LLM provider components for clarity and improved structure.
- Added support for JSON schemas in LLM requests, enabling structured responses.
- Introduced API key handling for LLM providers.
- Removed pip from SDK dependencies and updated uv.lock.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.2.2] - 2025-08-22

### Platform Release

This release includes the following component versions:
- **Backend 0.2.2**
- **Frontend 0.2.2**
- **SDK 0.2.2**

### Summary of Changes

**Backend v0.2.2:**
- Added document content extraction endpoint and document support to the `/test-sets/generate` endpoint, enabling processing of `.docx`, `.pptx`, and `.xlsx` formats.
- Implemented Redis authentication and updated environment configuration for enhanced security and management.
- Improved Docker configuration and startup scripts for a more robust and streamlined deployment process.
- Enhanced error handling for foreign key violations and improved consistency across backend routes, particularly for UUID validation and demographic routers.
- Added unit tests for backend components.


**Frontend v0.2.2:**
- Improved document upload experience with automatic metadata generation and updated supported file extensions.
- Enhanced project creation and management, including fixes for project name truncation and automatic refreshing after creation.
- Refactored and improved form validation and UI elements across the application.
- Updated Docker configuration for production mode and improved startup scripts.


**SDK v0.2.2:**
- Migrated document extraction from docling to markitdown, adding support for docx, pptx, and xlsx formats.
- Removed support for .url and .youtube file extensions.
- Improved code style and consistency with automated linting and formatting.


See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.2.1] - 2025-08-08

### Platform Release

This release includes the following component versions:
- **Backend 0.2.1**
- **Frontend 0.2.1**
- **SDK 0.2.1**
- **Polyphemus 0.1.0**

### Summary of Changes

**Backend v0.2.1:**
- Added support for filtering test sets related to runs and document upload functionality via `/documents/upload` endpoint.
- Enhanced test generation with optional documents parameter and improved response models.
- Added test result statistics support and "last login" functionality.
- Fixed document validation, GUID import issues, and Auth0 user handling.

**Frontend v0.2.1:**
- Introduced Test Results functionality for viewing and analyzing test outcomes.
- Added interfaces for handling test results statistics.
- Fixed infinite loading issues for test sets and updated contributing guides.

**SDK v0.2.1:**
- Added `get_field_names_from_schema` method to `BaseEntity` class for dynamic property access.
- Updated default base URL for API endpoint and improved documentation.

**Polyphemus v0.1.0:**
- Initial release of the LLM inference and benchmarking service.
- FastAPI-based REST API with Dolphin 3.0 Llama 3.1 8B model support.
- Modular benchmarking suite and OWASP-based security test sets.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)
- [Polyphemus Changelog](apps/polyphemus/CHANGELOG.md)

## [0.2.0] - 2025-07-25

### Platform Release

This release includes the following component versions:
- **Backend 0.2.0**
- **Frontend 0.2.0**
- **SDK 0.2.0**

### Summary of Changes

**Backend v0.2.0:**
- Enhanced team invitation process with improved security, validation, rate limiting, and email uniqueness checks.
- Implemented email-based notification system for test execution results.
- Improved test execution framework with sequential execution, configuration options, and enhanced task orchestration using Redis.
- Fixed issues related to OData filtering validation, JWT expiration, test set downloads, and score calculation for metrics.

**Frontend v0.2.0:**
- Added version information display to the frontend.
- Introduced a new team invitation flow with enhanced security and validation, including email uniqueness checks, rate limiting, and max team size.
- Improved session management with server logout upon session expiration and redirection to the home page.
- Numerous bug fixes and UI improvements across various components, including test sets, test runs, endpoints, and dark mode contrast.

**SDK v0.2.0:**
- Added support for `.txt` files to the `DocumentExtractor`.
- Introduced `documents` parameter to `PromptSynthesizer` for enhanced document handling.
- Added functionality for custom behaviors informed by prompts to the `PromptSynthesizer`.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.2.0] - 2025-07-25

### Platform Release

This release includes the following component versions:
- **Backend 0.2.0**
- **Frontend 0.2.0**
- **SDK 0.2.0**

### Summary of Changes

**Backend v0.2.0:**
Version 0.2.0 introduces a new team invitation feature with improved security and validation, including email uniqueness checks, rate limiting, and team size restrictions. This release also includes significant refactoring and improvements to the test execution and evaluation process, leveraging Redis for worker infrastructure and adding email-based notifications for test completion.

**Frontend v0.2.0:**
Version 0.2.0 introduces a new component for displaying version information and makes environment variables available to the client. This release also includes improvements to team invitation security and validation, as well as numerous bug fixes and UI enhancements across various components like test sets, test runs, and endpoints.

**SDK v0.2.0:**
Version 0.2.0 introduces enhanced document handling with .txt file support in the DocumentExtractor and a new `documents` parameter for the PromptSynthesizer. This release also adds custom behavior informed by prompts, allowing for more flexible and tailored content generation.

See individual component changelogs for detailed changes:
- [Backend Changelog](apps/backend/CHANGELOG.md)
- [Frontend Changelog](apps/frontend/CHANGELOG.md)
- [SDK Changelog](sdk/CHANGELOG.md)



## [0.1.0] - 2025-05-15

First release of the Rhesis main repo, including all components. Note that the SDK was previously developed separately and is now at version 0.1.8 internally, but is included in this repository-wide v0.1.0 release.

### Added
- **Backend v0.1.0**
  - Core API for test management
  - Database models and schemas
  - Authentication system with JWT
  - CRUD operations for main entities
  - API documentation with Swagger/OpenAPI
  - PostgreSQL integration
  - Error handling and logging

- **Frontend v0.1.0**
  - Next.js 15 with App Router
  - Material UI v6 component library
  - Authentication with NextAuth.js
  - Protected routes and middleware
  - Dashboard and test management interface
  - Test visualization and monitoring
  - Dark/light theme support
  - Responsive design

- **SDK v0.1.8** (see [SDK Changelog](sdk/CHANGELOG.md) for detailed history)
  - Test set management and generation capabilities
  - Prompt synthesizers for test case generation
  - Paraphrasing capabilities
  - LLM service integration
  - CLI scaffolding
  - Documentation with Sphinx

### Infrastructure
- Docker containerization for all services
- CI/CD pipeline setup
- Development environment configuration

### Changed
- Migrated SDK from its standalone repository (https://github.com/rhesis-ai/rhesis-sdk) into the main repo
- Updated repository structure to accommodate all components

### Note
- The SDK was previously developed and released (up to v0.1.8) in a separate repository at https://github.com/rhesis-ai/rhesis-sdk
- While the SDK is at version 0.1.8 internally, it's included in this repository-wide v0.1.0 release tag
- After this initial release, each component will follow its own versioning lifecycle with component-specific tags

[Unreleased]: https://github.com/rhesis-ai/rhesis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/v0.1.0

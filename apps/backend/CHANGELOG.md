# Backend Changelog

All notable changes to the backend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] - 2026-04-23

### Changed

- feat: Rhesis Architect — AI agent for test suite design and execution (#1671)

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

* style(frontend): apply prettier formatting to architect components
- feat: set default model IDs in user settings during local initialization (#1669)

Apply default language and embedding model IDs to user settings during local_init to match API onboarding behavior
- fix: sync topic relationship after FK updates (#1664)
- Fix Garak probe-coupled detectors and improve pipeline reliability (#1662)

* fix(sdk): normalize detector paths and handle probe-coupled context

Add path normalization so short-form detector paths from the DB
(e.g. encoding.DecodeMatch) match the full-form keys in
CONTEXT_REQUIRED_NOTES. Register DecodeMatch, DecodeApprox, and
AttackRogueString in detectors.yaml with required_note. Replace
NaN scores with None for PostgreSQL JSONB compatibility. Add
probe_notes to factory ACCEPTED_PARAMS.

* fix(backend): inject probe notes for garak detectors

Add _inject_probe_notes with path normalization so garak_notes from
test_metadata reach probe-coupled detectors regardless of whether the
DB stores short or full detector paths. Extract per-prompt notes from
encoding/promptinject probes at import time and store them in
test_metadata. Add backfill migrations for existing test data.

* test(tests): add garak detector smoke, pipeline, and e2e tests

Add SDK smoke tests for all 20 registered detectors with safe/unsafe
inputs. Add backend pipeline tests verifying garak_notes flow through
_inject_probe_notes, MetricFactory, and evaluate. Add e2e tests
exercising every detector through the real prepare_metrics pipeline
including short-path variants that mirror production DB values.

* feat(frontend): add search for garak probes in import dialog

Add a search field that filters modules and probes by name,
description, category, and topic. Select All/Deselect All now
operates on the visible (filtered) probes. Empty results show
a clear "no matches" message.

* fix(garak): exclude visual_jailbreak module to prevent image downloads

FigStep and FigStepFull probes download ~400 images from GitHub during
instantiation. Since _extract_prompts_and_notes instantiates every probe
class, this caused hundreds of HTTP requests on every cache miss.

Exclude visual_jailbreak from enumeration (image-only payloads have no
meaningful text representation in Rhesis) and bump SCHEMA_VERSION to 5
to invalidate any cached data built with the old module set.

* refactor(garak): address staff engineer review findings

- Fix: inconclusive MetricResult (score=None, inconclusive=True) was
  collapsed to is_successful=False by LocalStrategy via ScoreEvaluator.
  Both _process_metric_result and _a_eval_one_with_retry now check the
  inconclusive flag first and pass is_successful=None through unchanged.

- Fix: deduplicate detector path normalisation into a single
  normalize_detector_path() helper in the SDK registry, plus an
  is_context_required() convenience function. Removes the duplicated
  inline logic in detector_metric.py and evaluation.py, and eliminates
  the direct CONTEXT_REQUIRED_NOTES import from the backend worker.

- Fix: _extract_prompts_and_notes now disables follow_prompt_cap when
  instantiating probes (same as the Alembic backfill migration) so the
  prompt→trigger map is deterministic and complete for encoding probes.

- Fix: pad prompt_notes with None when len(triggers) < len(prompts) so
  prompt_notes[i] always corresponds to prompts[i].

- Fix: migration downgrade() now requires test_metadata ? 'garak_notes'
  to avoid removing legitimately-set notes on rows untouched by upgrade.

- Fix: replace fragile assert len(DETECTORS) == 20 with a structural
  invariant test that survives YAML additions.

- Fix: SCHEMA_VERSION comment now documents both reasons for v5.

- Test: add TestLocalStrategyInconclusivePassthrough to cover the
  inconclusive passthrough path end-to-end (23 tests, all green).

* style(backend): fix ruff formatting in service.py and result_builder.py

* fix(garak): address peqy review comments

- Fix: notes or self._probe_notes treated explicit {} as falsy, silently
  falling back to stored probe notes. Changed to notes if notes is not
  None else self._probe_notes so callers can pass {} to intentionally
  provide no context without being overridden.

- Fix: _inject_probe_notes early-exit used 'if not probe_notes' which
  also treated {} as 'no injection'. Changed to 'if probe_notes is None'
  to consistently distinguish explicit empty from absent.

- Fix: trigger/prompt count mismatch in _extract_prompts_and_notes was
  silently dropping extra triggers. Added a warning log so mismatches
  are surfaced rather than hidden.

- Fix: migration downgrade() now also checks
  'test_metadata->'garak_notes' ? 'triggers'' to avoid removing notes
  that were not set by the migration (e.g. unrelated garak_notes keys).
  Applied to both promptinject and encoding migrations.

* fix(garak): address second peqy review round

- Fix: inconclusive reason message now checks whether the required note
  key is actually present and non-empty in effective_notes, not just
  whether effective_notes is truthy. Catches cases where notes={} or
  notes={"wrong_key": ...} were silently producing the generic message.

- Fix: _inject_probe_notes reverts early-exit to 'if not probe_notes'
  (empty dict = nothing to inject) and adopts a non-destructive merge:
  probe_notes is only set when the key is absent from existing parameters,
  so a pre-populated MetricConfig is never silently overwritten.

- Fix: _extract_prompts_and_notes logs the exception (with traceback) at
  DEBUG level instead of silently returning ([], []), making probe
  instantiation failures visible during enumeration.

- Fix: encoding backfill migration normalises prompt text with .strip()
  and \r\n→\n before key lookup so whitespace/line-ending differences
  between DB storage and generated prompts no longer cause silent misses.

* style(sdk): apply ruff formatting to detector_metric.py

* style(backend): apply ruff formatting to encoding backfill migration
- Temporarly disable default embedding model selection (#1661)

* fix(api): reject models.embedding in PATCH /users/settings

* fix(models-ui): remove embedding default toggle and clarify copy

* docs: add comment for future reference
- docs: update frontend and backend README and CONTRIBUTING (#1654)

* docs: simplify and update the backend README

* docs: remove backend CONTRIBUTING

Remove CONTRIBUTING.md in apps/backend in favour of a single CONTRIBUTING on the main folder

* docs: remove frontend contributing guide

* docs: add command for starting worker

* docs: add smaller backend contributing guide

* docs: trim down frontend readme and contributing guide

* docs: remove type-check and add uv install

* docs: remove playwright since there are no e-2-e tests

* docs: add instructions for e2e frontend testing
- Add adaptive testing embeddings and diversity-aware suggestions (#1656)

* feat: add adaptive testing embedding support

- Backend: CreateAdaptiveTestBody, optional embedding on create and suggestion generation, embeddings service module
- Frontend: generate_embedding / generate_embeddings flags and types
- Tests: route coverage for new behavior
- Worker: uv.lock resolution bump

* feat: add diversity scoring to adaptive testing suggestions

- Backend: Introduced `diversity_score` to `SuggestedTest` and implemented `sort_by_diversity` function to rank suggestions based on Euclidean distance from centroid embeddings.
- Frontend: Updated `SuggestionsDialog` to display diversity scores in tooltips for better user insight.
- API: Updated interface to include optional `diversity_score` in suggestions response.

* feat: implement async embedding and suggestion generation

- Backend: Refactored `generate_suggestions` and `generate_suggestions_endpoint` to support async operations, improving performance during suggestion generation.
- Added `a_generate_embedding_vector` for async embedding of text, enhancing the embedding service's capabilities.
- Updated embedding calls in suggestion generation to utilize the new async method, allowing for concurrent processing of embeddings.
- Frontend: Adjusted embedding generation flags to prevent manual test embeddings until full support is implemented.

* feat: enhance embedding service with batch processing and resolver

- Added `resolve_embedder` function to streamline embedding model resolution for users, reducing database lookups.
- Introduced `a_generate_embedding_vectors_batch` for concurrent embedding of multiple texts, improving performance.
- Updated `generate_suggestions` to utilize the new batch embedding method, enhancing suggestion generation efficiency.

* feat: implement unified suggestion pipeline for adaptive testing

- Added a new endpoint `/suggestion_pipeline` to handle a unified process for generating suggestions, invoking endpoints, and evaluating results in a single NDJSON stream.
- Introduced `SuggestionPipelineRequest` schema to encapsulate parameters for the pipeline.
- Updated frontend to utilize the new pipeline, streamlining the suggestion generation and evaluation process.
- Enhanced backend services to support concurrent evaluation and output streaming, improving overall performance and user experience.

* feat: implement streaming suggestion generation and progress tracking

- Added support for streaming individual suggestions and embeddings from the LLM in the backend, enhancing real-time feedback during suggestion generation.
- Updated the `SuggestionsDialog` component in the frontend to track and display the progress of test generation, including completed suggestions and total expected.
- Introduced new event types for streamed suggestions and embeddings in the API, allowing for a more interactive user experience.
- Refactored existing interfaces to accommodate the new streaming functionality, improving overall architecture and maintainability.

* refactor: update suggestion pipeline logging and event structure

- Modified the logging format in the suggestion pipeline to include timestamps for better tracking of events.
- Adjusted the `PipelineEmbeddingEvent` interface to only include the index, removing the embedding vector for a more streamlined event structure.
- Updated the `SuggestionsDialog` component to reflect changes in the event handling and total counts for outputs and metrics, enhancing the user experience during suggestion generation.

* refactor: clean up imports and enhance diversity scoring in adaptive testing

- Removed unused imports and reorganized import statements for better readability across several files.
- Updated the `diversity_score` description in the `SuggestedTest` schema to clarify its calculation method.
- Introduced a new module for adaptive testing diversity strategies, implementing both Euclidean and Cosine centroid diversity metrics.
- Added unit tests for the new diversity strategies to ensure correct functionality and integration with existing suggestion sorting logic.

* next

* feat: enhance suggestion pipeline with diversity scores

- Updated the suggestion pipeline to include `diversity_scores` alongside `diversity_order`, providing additional metrics for sorted suggestions.
- Modified the `SuggestionsDialog` component to handle and display diversity scores, ensuring alignment with the updated backend event structure.
- Adjusted the `PipelineSuggestionsDoneEvent` interface to reflect the new diversity scores, improving the API's clarity and usability.

* refactor: clean up formatting in SuggestionsDialog and related files

- Improved code readability by adjusting formatting in the SuggestionsDialog component, including consistent line breaks and indentation.
- Streamlined the handling of suggestion outputs and tooltip content for better clarity and maintainability.
- Minor adjustments in the LiteLLM and RhesisEmbedder classes to enhance code consistency across the SDK.
- Fix model connection endpoint passthrough (#1643)

* fix(backend): pass endpoint and use correct api_base param

Forward the endpoint URL when testing model connections and rename
the extra_params key from base_url to api_base to match the
provider SDK expectations.

* fix(sdk): forward extra_params from model config

Merge extra_params from ModelConfig into kwargs in get_model so
custom endpoint URLs and other provider-specific settings are
passed through to the underlying LLM client.
- Add flexible model selection and execution model support (#1642)

* feat(backend): add execution model and model override

Introduce separate execution and evaluation model resolution
throughout the backend. Add DEFAULT_EXECUTION_MODEL env var,
split the single model parameter into execution_model and
evaluation_model across batch/sequential execution paths,
and support per-request model override for test generation,
execution, and rescoring. Add custom test count validation
capping at 200 tests.

* feat(frontend): add model selector and custom test count

Add reusable ModelSelector component with provider icons and
default model resolution. Integrate execution and evaluation
model selection into test-set execution, test-run, and rerun
drawers. Add execution model default option to the models
settings page. Replace misleading test count ranges with exact
numbers and add custom slider option (1-200) with validation.

* feat(sdk): add execution model and model override support

Add set_default_execution method to Model entity. Update
TestSet.execute and TestSet.rescore to accept execution_model_id
and evaluation_model_id parameters for per-request model override.

* test(tests): add tests for model override and execution model

Add unit tests for generation/execution/evaluation model override
resolution, execution validation with execution model, rescore
with evaluation model override, and SDK model/test-set execute
methods. Update existing tests to use split model parameters.

* ci: add DEFAULT_EXECUTION_MODEL to deploy configs

Add DEFAULT_EXECUTION_MODEL environment variable to GitHub Actions
backend and worker workflows, worker k8s deployment, and
infrastructure secret configuration scripts.

* fix(frontend): restore model selection on test re-run

Initialize execution and evaluation model selectors from the
original test configuration attributes when re-running a test,
so users see the models that were previously used.

* fix(backend): address PR review feedback from peqy

- Remove duplicate test methods in test_rescore.py that caused
  Python to silently overwrite earlier definitions
- Add default model fallback in batch and sequential except blocks
  so models never stay None on resolution failure
- Validate per-request model_id override in generation router to
  return a clear 400 instead of a 500 for invalid models

* fix(tests): update test_set execution mock assertion

Add execution_model_id and evaluation_model_id kwargs to the
_create_test_configuration mock assertion to match the updated
service signature.

* fix: address remaining PR review feedback

- Add safe fallback for theme.iconSizes in ModelSelector to prevent
  errors when rendered outside the app's custom theme
- Add model override validation to multi-turn generation endpoint
  for consistency with the single-turn endpoint

* docs: update documentation for flexible model selection

Add execution model as a third model purpose, update test generation
size options to exact counts with custom slider, add
DEFAULT_EXECUTION_MODEL to deployment guides, document model settings
in execution drawer, and add SDK execute/rescore model params.
- Fix trace metrics test mocks for idempotency guard (#1640)

* perf(telemetry): skip redundant turn evaluation and enrichment re-runs

Add idempotency guard to evaluate_turn_trace_metrics: skip if
trace_metrics_processed_at is already set and turn_metrics exist on the
span. Uses processed_at (not just turn_metrics) so spans whose I/O
attributes hadn't arrived yet still get a retry on the next pass.

Replace naive enriched_data truthiness check in TraceEnricher with a
smart cache: re-enrich only when spans with processed_at=None are present
(new spans arrived since the last pass). This allows the progressive
enrichment pattern (root → + LLM child spans → full fields) while
stopping redundant re-runs once all spans are processed.

* fix(tests): set mock span idempotency attrs explicitly

The perf(telemetry) commit added an idempotency guard that checks
trace_metrics_processed_at and turn_metrics on root spans. MagicMock
auto-creates these as truthy objects, causing the guard to always
trigger and return already_evaluated. Set both to None/{} by default.
- fix(exchange_rate): update API URL and enhance fallback caching logic (#1637)

- Changed API URL from api.frankfurter.app to api.frankfurter.dev due to redirection.
- Implemented caching of fallback exchange rate to avoid repeated API calls when the network is unavailable.
- Updated tests to verify caching behavior for fallback rates.
- feat(telemetry): add retry with exponential backoff to exporter (#1605)

* feat: repurpose rhesis meta-package as lightweight telemetry foundation

Signed-off-by: Alex Maggioni <98940667+AlexMaggioni@users.noreply.github.com>

* ci: add pre-commit hook for packages/rhesis

Signed-off-by: Alex Maggioni <98940667+AlexMaggioni@users.noreply.github.com>

* feat(telemetry): add retry with exponential backoff to exporter

Use tenacity's Retrying class to retry transient export failures
(ConnectionError, Timeout, HTTP 429/503) with exponential backoff
and jitter. Client errors (4xx) are not retried. Defaults to 3
attempts, configurable via max_retries.

* test(telemetry): add retry logic tests for exporter

Cover retry behavior for transient failures:
- Retry on ConnectionError, Timeout, 429, 503 then succeed
- Exhaust retries on persistent ConnectionError
- No retry on 422 and 401 (non-transient errors)
- Failure counters increment after exhausted retries
- Success resets consecutive failure counter

Signed-off-by: Alex Maggioni <98940667+AlexMaggioni@users.noreply.github.com>

* chore: drop stale artifacts superseded by #1603 review

The squash-merged version of #1603 (a484563b) reworked two things
that the original branch commits on this branch do not reflect:

- packages/rhesis/uv.lock: standalone lockfile is unused; the rhesis
  package is locked transitively from sdk/uv.lock and apps/backend/uv.lock
- apps/backend/pyproject.toml: drop the direct
  rhesis = { path = "../../packages/rhesis" } source override; the
  backend now picks up rhesis transitively via rhesis-sdk[telemetry]

* style(telemetry): align test imports with project ruff config

The project's ruff isort config does not list rhesis.telemetry as
known-first-party (only rhesis.sdk/backend/penelope/polyphemus), so
the rhesis.telemetry import belongs in the same group as the other
third-party imports. Removes the stray blank line introduced during
the upstream/main merge resolution.

Signed-off-by: Alex Maggioni <98940667+AlexMaggioni@users.noreply.github.com>

* fix(telemetry): unwrap tenacity RetryError in exporter retries

The retryer raised tenacity.RetryError on exhaustion, which export()
did not catch — exhausted ConnectionError/Timeout and persistent
429/503 fell into the generic "This is a bug" branch instead of the
matching error handlers. Install a retry_error_callback that calls
Future.result() on the last attempt: re-raises the original exception
for exception-retries, returns the last Response for result-retries
(which raise_for_status() then converts to HTTPError).

Also extend the retryable status set to include 408, 502 and 504 —
all standard transient errors that proxies emit and that the existing
ConnectionError/Timeout handlers do not cover (a 502/504 is a complete
HTTP response, not a client-side network failure).

Extract _RETRYABLE_STATUSES as a class constant and a _record_failure()
helper to centralize the failure-counter bookkeeping shared by every
except branch in export().

Tests strengthened to assert the correct error branch is hit on
exhaustion (not the generic "This is a bug" path), plus coverage for
408/502/504 retry-then-success and a 500-not-retried regression guard.

* fix(telemetry): tighten exporter retry edge cases

- Guard HTTPError.response None: a bare HTTPError without a response
  attribute would raise AttributeError inside the handler and get
  reclassified as "This is a bug" by the catch-all. Read status_code
  defensively so the matching branch still fires.
- Log the upcoming sleep duration in _log_retry: state.idle_for is
  cumulative across attempts and over-reports on retry 2+. Use
  next_action.sleep so the message reflects the actual next wait.
- Mock the retryer wait in test_export_timeout: the pre-existing test
  didn't anticipate retries and was waiting on real exponential
  backoff (~3-7s). Patch _retryer.wait the same way the new retry
  test class does so the suite stays fast.

* refactor(telemetry): align exporter retry semantics with upstream OTLP

Tighten the tenacity-based retry loop in RhesisOTLPExporter so it
matches the deadline-bounded, shutdown-aware behavior that upstream
OTLPSpanExporter implements internally — without abandoning tenacity
or rewriting the exporter from scratch.

Changes:
- Rename max_retries -> max_attempts; the value is a hard backstop,
  not the actual budget. The deadline is now the real budget.
- Drop the misleading self._timeout reassignment after super().__init__;
  the parent already stores it.
- Broaden _RETRYABLE_STATUSES to {408, 429} | range(500, 600). Mirrors
  upstream OTLP _is_retryable() and additionally retries 429 (which
  upstream skips).
- Add stop_after_delay(timeout) so a slow chain of retries can't
  overshoot the export wall-time budget. attempts | delay | shutdown
  are OR-composed so whichever fires first wins.
- Add a cooperative shutdown path: a threading.Event set by an
  override of shutdown(), checked by a custom stop predicate AND used
  as the tenacity sleep callback (Event.wait), so an in-flight backoff
  unblocks immediately when the SDK is torn down.
- Per-attempt timeout shrinks with the remaining deadline via a closure
  over time.monotonic(), so a slow first attempt cannot let a second
  attempt overshoot the budget.

Tests: 11 new cases covering deadline exhaustion, cross-thread shutdown
during backoff, the per-attempt budget shrinking invariant, broadened
5xx retry coverage, and the SSLError-is-ConnectionError gotcha. One
test flipped from no_retry_on_500 to retry_on_500_then_succeed to
match the new (correct) retryable set.

* docs(telemetry): trim verbose comments and docstrings

Drop paragraph-style block comments and multi-paragraph test
docstrings that restated what the code/asserts already say. Keeps
the focused 1-2 line comments that flag real footguns (e.g. the
next_action.sleep vs idle_for note in _log_retry).

* test(telemetry): collapse duplicated exporter tests via parametrize

Per-status-code test bodies were near-identical — only the integer
differed. Collapse into three parametrized tests:

- test_retry_on_retryable_status_then_succeed → [408, 429, 500-504]
- test_no_retry_on_non_retryable_status → [400, 401, 422]
- test_exhaust_retries_on_persistent_status → [503, 429]

Same for the two retryable transport exceptions (ConnectionError,
Timeout), now covered by a single parametrized success test and a
single parametrized exhaustion test.

Also drop two trivial helper tests that were already covered
transitively by the integration tests:

- test_shutdown_method_sets_event
- test_stop_on_shutdown_predicate

Net: ~150 lines removed, 25 new test functions → 12 functions
expanding to 23 parametrized cases, 36 → 34 total tests.

* fix(telemetry): own _timeout to decouple from parent and respect timeout=0

The deadline closure in export() reads self._timeout, which was
inherited from the parent OTLPSpanExporter's __init__. Two problems:

1. Fragile dependency on a private attribute. If upstream renames
   _timeout, our deadline math silently breaks.

2. The parent uses `timeout or float(env_default)`, so a caller
   passing timeout=0 gets silently rewritten to the env default
   (10s). The closure was lying about the budget while tenacity's
   stop_after_delay (constructed from the constructor arg directly)
   correctly saw 0.

Assign self._timeout = timeout in __init__ so we own the attribute
and timeout=0 means 0 in the deadline math.

Tighten test_deadline_stops_loop_before_attempt_cap to assert
call_count == 0 — with the fix, the closure deadline guard preempts
the very first post instead of relying on stop_after_delay to fire
after one wasted attempt.

---------

Signed-off-by: Alex Maggioni <98940667+AlexMaggioni@users.noreply.github.com>
- refactor: duplicate get_or_create_status() (#1635)

* refactor(uuid): move safe_uuid_convert() to centralized utils folder

- Create a new utility function to_uuid() that can be used across the backend

* refactor(crud_utils): replace verbose try/except block with new utility function

* fix: convert safely to UUID

* refactor(uuid): correct import using new centralized utility function

* refactor(safe_uuid_convert): keep old function name

* refactor: consolidate get_or_create_status into crud_utils

- Removed the duplicate get_or_create_status function from status.py in favor of the existing implementation in crud_utils.py
- Updated all call sites to use explicit keyword arguments (e.g., organization_id=...) to account for the optional description parameter in the crud_utils signature

* refactor(status): delete file missing from last merge
- fix/uuid conversion (#1632)

* refactor(uuid): move safe_uuid_convert() to centralized utils folder

- Create a new utility function to_uuid() that can be used across the backend

* refactor(crud_utils): replace verbose try/except block with new utility function

* fix: convert safely to UUID

* refactor(uuid): correct import using new centralized utility function

* refactor(safe_uuid_convert): keep old function name

* fix(user_id): use UUID contructor to raise error in case of invalid UUID
- fix: email sending is not working on the test generation completion (#1633)
- Fix vulnerable dependencies flagged by pip-audit (#1627)

* fix(deps): update vulnerable packages flagged by pip-audit

Upgrade transitive and direct dependencies with known CVEs:
- aiohttp 3.13.3 -> 3.13.5
- cryptography 46.0.5 -> 46.0.6
- langchain-core 1.2.14/1.2.17 -> 1.2.24
- nltk 3.9.3 -> 3.9.4
- pygments 2.19.2 -> 2.20.0
- requests 2.32.5 -> 2.33.1
- pdfminer-six 20250506 -> 20260107
- jaraco-context 6.0.1 -> 6.1.2
- streamlit 1.51.0 -> 1.56.0

Also adds exclude-newer = "1 week" to all pyproject.toml files,
the pip-audit aggregate script, and relaxes cryptography/litellm
lower bounds.

Skipped: fastmcp (major bump), diskcache/lupa (no fix available).

* chore(deps): update cryptography dependency to version 46.0.5 across multiple projects

This commit updates the cryptography package version from 46.0.0 to 46.0.5 in the pyproject.toml and uv.lock files for the research assistant, backend, and sdk applications. Additionally, it adjusts the exclude-newer timestamps in the uv.lock files to reflect the new versioning.



## [0.6.11] - 2026-04-09

### Added
- Implemented core embedding generation services and tasks for generating and storing vector embeddings, with deduplication and stale embedding cleanup.
- Added automatic source chunking service to persist chunks to the database, with soft-delete and re-chunking support.
- Introduced a lightweight `rhesis-telemetry` package for telemetry foundation.
- Added an AsyncService base class for async/sync task orchestration.
- Implemented a built-in "echo" use case that returns the user's input verbatim without invoking the LLM or consuming any rate-limit quota.
- Added a cancel test run endpoint to revoke Celery tasks and set the status to Cancelled.
- Added mid-flight cancellation via asyncio watchdog.
- Added adaptive testing settings endpoints to manage default endpoint and metric assignments.
- Added "Tests without topic" option in AdaptiveTestingDetail for adaptive testing.
- Added Chunk entity and CRUD operations.
- Added user feedback functionality for adaptive testing suggestion generation.
- Added streaming for suggestion generation and evaluation in adaptive testing.
- Added export functionality for adaptive test sets to create regular test sets.

### Changed
- Replaced chord fan-out with async batch execution engine for test execution.
- Switched Celery worker from prefork to threads pool.
- Enhanced adaptive testing components and UI elements.
- Improved adaptive testing suggestions and metrics.
- Optimized batch execution performance.
- Improved adaptive testing suggestion prompt and generation.
- Improved adaptive testing settings flow and test feedback.
- Streamlined adaptive testing suggestion generation and removed unused functions.
- Enhanced suggestion prompt structure and clarity for adaptive testing.
- Updated default sort order for test retrieval from ascending to descending in adaptive testing.
- Refactored adaptive testing detail and suggestions dialog components.

### Fixed
- Fixed circular import.
- Fixed build metric configs before session closes.
- Fixed concurrent embedding insertion race condition.
- Fixed entity_id to send to Celery to always be a JSON-serializable string.
- Fixed deletion strategy and chunk ownership in chunking service.
- Fixed DB transaction issue in auto_chunk_source.
- Fixed chunk update when source.content is empty.
- Fixed build metric configs before session closes.
- Fixed bugs in batch engine and invoker layer.
- Fixed negative duration on failed test runs.
- Fixed raw HTML parsing in markdown.
- Fixed telemetry tasks binding to redis celery app.
- Fixed telemetry ingestion error logging.
- Fixed file import issues: XLSX/CSV parsing, Turn Config support, test-type mismatch warning.
- Fixed tests that need the status_id parameter.
- Fixed auth manager mock target to `_token_session.post`.
- Fixed misleading default=dict from nullable metadata columns.
- Fixed unique index for active chunks and remove server default.
- Fixed organization deletion of embeddings referencing status before status deletion.
- Fixed imports.
- Fixed thread-safety race in `_get_file_logger`.
- Fixed missing `status_id` migration in embedding table.
- Fixed reference when backfilling `status_id`.
- Fixed tests for Source entity, add tests for Trace and Chunk.
- Fixed all_cancelled falsy check in batch execution.
- Fixed broken tests in invoker layer.
- Fixed RPC close bug and eliminated per-invocation object construction.

### Removed
- Removed misleading "(SIGTERM)" in cancel_test_run docstring.
- Removed duplicate backend rhesis dependency in favor of transitive rhesis[telemetry] via the SDK.


## [0.6.10] - 2026-03-26

### Added
- Added trace metrics evaluation system with Celery tasks for per-turn and per-conversation metric evaluation, including configurable debounce for conversation-level evaluation.
- Added trace review system with human review overrides for traces, turns, and individual metrics, including overall status recalculation.
- Added SQL-level trace metrics aggregation (`get_trace_metrics_aggregated`) replacing Python-side processing for improved query performance.
- Added Trace scope to MetricScope lookup type, enabling metrics to target traces.
- Added `trace_metrics_status_id` column on Trace model for evaluation status tracking.
- Added `trace_reviews` JSONB column on Trace model for storing human review data.
- Added task and comment endpoints for traces via the telemetry router.
- Added trace metrics cache service for caching project metric configurations.
- Added `project.attributes` JSONB column for storing project-level trace metric assignments.

### Changed
- Consolidated review target constants into a `ReviewTarget(str, Enum)` for type safety across test result and trace review systems.
- Consolidated `MetricScope` enum definition, removing duplication between app schemas and task constants.
- Replaced hardcoded entity type strings with `EntityType` enum constants.
- Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` across trace review and telemetry code.
- Sanitized API error messages in telemetry endpoints to prevent internal details from leaking to clients.
- Refined Celery retry strategy to only retry on transient errors (IOError, ConnectionError, SoftTimeLimitExceeded).
- Added soft and hard time limits to trace evaluation Celery tasks.
- Extracted shared `_prepare_evaluation` helper to reduce duplication in evaluation tasks.
- Decoupled trace enrichment from evaluation into separate services.

### Fixed
- Fixed `recalculate_overall_status` to correctly account for turn overrides in overall pass/fail determination.
- Fixed `rollback_initial_data` to nullify `trace_metrics_status_id` before deleting Status rows, preventing FK constraint violations.
- Fixed multi-turn trace metric filtering to correctly scope metrics.
- Fixed default evaluation model resolution for trace metrics.
- Corrected docstring mismatch for worker cache TTL value.

## [0.6.9] - 2026-03-23

### Added
- Added the ability to delete adaptive testing test sets.
- Added a stats API for test runs and test results, accessible via the SDK.
- Exposed test execution context (test_id, test_run_id, test_configuration_id) in request mapping templates.
- Added an "overwrite" parameter for adaptive testing output generation and evaluation, allowing users to regenerate outputs/evaluations for existing tests.
- Implemented NIST-aligned password hardening with zxcvbn strength scoring, context-specific word blocking, and HaveIBeenPwned breach checks. Minimum password length raised to 12 characters.
- Added an attachments column to the tests grid, displaying the number of attached files.
- Added dedicated documentation pages for importing test sets from CSV/Excel/JSON/JSONL files and from the Garak LLM vulnerability scanner.
- Added a public `format_conversation` API to the metrics module for formatting conversation history.
- Added SendGrid API key and email template ID variables to the service secrets configuration.
- Added evaluate endpoint and UI for adaptive testing.
- Added a GET /test_runs/{id}/metrics endpoint that returns the distinct metric names actually evaluated in a test run.
- Added a public POST /feedback backend endpoint (no auth required).

### Changed
- Improved backend performance by replacing Python-side aggregation with SQL queries, adding database views and indexes, and reducing redundant work per request.
- Refactored metric evaluation process using a strategy pattern for improved flexibility and maintainability.
- Centralized enum constants and fixed migration syntax for test result statuses.
- Updated Celery worker configuration to improve concurrency settings.
- Refactored MetricEvaluator and utility functions for improved configuration handling.
- Moved feedback and polyphemus emails to the backend EmailService.
- Made `format_conversation` public and handle tool-call-only assistant messages.
- Updated password policy UI and error handling to align with new backend policy.
- Replaced ToxicCommentModel with PerspectiveToxicity for do-not-answer and toxicity detection.
- Updated the adaptive testing evaluation process to utilize the MetricEvaluator class.
- Improved format_conversation: public API and tool-call-only message support.
- Refactored metric configuration handling in evaluator.
- Transitioned to strategy pattern for metric evaluation.

### Fixed
- Fixed test run stats display by using `metadata.total_test_runs` for empty-state check.
- Fixed `result_distribution` to count actual test results instead of execution status.
- Fixed "no runs yet" flicker on test-runs page.
- Fixed the issue where calculating the pass rate for a test run relied on `first()` returning the correct `Status` record.
- Fixed welcome email not being sent on email/password and magic link sign-up.
- Fixed metadata rendering in multi-turn metric evaluation.
- Fixed the filter layout on the metrics overview page.
- Fixed counts including soft-deleted records.
- Fixed MCP auth to use the system default model.
- Fixed onboarding StaleDataError caused by RLS session variable loss after db.commit().
- Fixed tests grid random reordering with stable secondary sort.
- Fixed a bug where advanced filters showed metrics from all linked behaviors, not just those evaluated in the current test run.
- Fixed a bug where selecting a metric produced 0 results because the name from behavior_metric_association did not match the JSONB key used at evaluation time.
- Fixed a bug where the format_number filter was never registered, causing a Jinja2 FilterError on every render.
- Fixed a bug where the backend `SessionMiddleware` was still referencing `AUTH0_SECRET_KEY`.
- Fixed a bug where the test_run_id metadata was not being added to TasksAndCommentsWrapper in TestResultDrawer.
- Fixed a bug where the ToxicCommentModel was not being substituted with PerspectiveToxicity in the SDK.
- Fixed a bug where the test_run_id metadata was not being added to TasksAndCommentsWrapper in TestResultDrawer.
- Fixed a bug where the Notion integration link was pointing to the external integrations page.
- Fixed a bug where the backend `SessionMiddleware` was still referencing `AUTH0_SECRET_KEY`.
- Fixed a bug where the test_run_id metadata was not being added to TasksAndCommentsWrapper in TestResultDrawer.

### Removed
- Removed Assignee and Owner from Test Run Configuration.
- Removed obsolete test_metric.py script.
- Removed temporary debug tooling for onboarding emails.

### Security
- Implemented dedicated SESSION_SECRET_KEY to adhere to the cryptographic key separation principle.
- Prevented fallback session secret in production.
- Hardened password policy with NIST-aligned guidelines.
- Updated vulnerable dependencies, including `next`, `PyJWT`, `pyasn1`, `orjson`, `tornado`, `langgraph`, and `mcp-atlassian`.


## [0.6.8] - 2026-03-12

### Added
- Added multi-target review annotations for test runs (turns, metrics, test results). Reviews can now override test metrics and turns, updating the test result status.
- Added @mention support in review comments, allowing users to mention metrics and turns.
- Added dynamic probe generation for garak LLM vulnerability scanner, enabling runtime prompt generation based on metadata.
- Added per-turn metadata, context, and tool_calls to conversation evaluation, enhancing conversational metrics.
- Added pagination, search, and filters to the projects list for improved project management.
- Added scheduled Day 1, Day 2, and Day 3 onboarding emails to guide new users.
- Added `@metric` decorator and connector protocol for SDK-side metric evaluation, enabling client-side metric execution.
- Added JSON logging support with `python-json-logger` for structured log analysis.
- Added configurable message size limit, idle timeout, and rate limiting to the WebSocket connector for enhanced security.

### Changed
- Renamed the default Penelope goal metric from `penelope_goal_evaluation` to `goal_achievement` for better alignment with the SDK.
- Refactored review override logic into a dedicated service module for improved maintainability.
- Refactored backend to use standard Python logging configuration instead of a custom logger.
- Upgraded garak LLM vulnerability scanner to v0.14.0 with Python 3.12 support.
- Made SDK model generation async-first for improved performance.
- Improved metric selection dialog with auto-focus search, comprehensive metric fetching, and consistent chip display.
- Converted RhesisLLM and VertexAILLM to async-first models with aiohttp integration.
- Updated TestRunHeader, TestsList, and overview tab to use effective status reflecting review overrides.
- Updated the WebSocket connector to decouple the endpoint from project/environment binding, enhancing flexibility.
- Renamed the Penelope documentation section to "Conversation Simulation" for clarity.

### Fixed
- Fixed an issue where test set execute button was disabled for manually created test sets.
- Fixed auto-configure to preserve mappings when LLM correction omits them.
- Fixed an issue where turns without criteria were not displaying pass/fail labels.
- Fixed a bug where the backend was not guarding against None in `_compute_review_state`.
- Fixed an issue where body styles were not restored on unmount during resize drag.
- Fixed an issue where the LLM correction call could overwrite valid mappings from the initial analysis.
- Fixed an issue where tests env vars were overwritten with .env values during the import chain.
- Fixed a bug in Python 3.12 where `str(Enum)` formatting produced unexpected output in tool descriptions.
- Fixed a bug where `renderMentionText` could not access the theme.
- Fixed an issue where the email scheduling was not working correctly.
- Fixed a bug where `add_message()` was storing the caller's dict by reference.
- Fixed an issue where duplicate project names were not disambiguated.
- Fixed an issue where metric scope filter was not working correctly.
- Fixed an issue where the logger configuration was being called multiple times.
- Fixed an issue where the logger was not set during application lifespan.
- Fixed an issue where the frontend was using null for ProjectsQueryParams.$filter type.
- Fixed an issue where the frontend was using string-sliced keys for context list items.
- Fixed an issue where the frontend was using invalid tool_calls data in deepeval test.
- Fixed an issue where the frontend was using emoji linter violation for penelope icon.

### Security
- Resolved 21 Dependabot security vulnerabilities by upgrading dependencies and adding npm overrides.
- Upgraded `langgraph-checkpoint` to 4.x to address CVE-2026-27794 (pickle deserialization RCE).


## [0.6.7] - 2026-03-05

### Added
- Added multi-file attachment support for tests, traces, and playground.
- Added file upload and removal functionality to the frontend for tests.
- Added file format filters and trace file linking for endpoint invocations.
- Added file upload support to the `/chat` endpoint.
- Added file attachment UI to Playground chat.
- Added file download functionality to `FileAttachmentList` and `MessageBubble`.
- Added file attachment support to multi-turn tests in Penelope.
- Added file attachment support to SDK entities.
- Added JSON and Excel file upload support to the Playground.
- Added metadata and context as collapsible sections in the Test Run detail view.
- Added trace drawer and file sections to the Test Run detail view.
- Added required field validation to the metric creation form.
- Added Azure AI Studio and Azure OpenAI provider support.
- Added optional parameters for `api_base` and `api_version` to LiteLLM and its derived classes.

### Changed
- Renamed file data field from `content_base64` to `data` for consistency.
- Moved the file attachment button inside the text input in Playground chat.
- Enhanced the Test Run detail view with improved UI and information display.
- Updated Node.js version to 24 in CI configurations and Dockerfiles.
- Updated SDK to use `exclude_none=True` in `BaseEntity.push()`

### Fixed
- Fixed an issue where `test_set_type_id` was missing when creating test sets from the manual writer.
- Fixed manual test writer test set association and navigation issues.
- Fixed focus loss in metric evaluation steps TextFields.
- Fixed an issue where lazy-load failures occurred in mixin relationship properties after deletion.
- Fixed an issue where raw db.query() was used in update_test_set_attributes.
- Fixed the file migration to rebase on the litellm provider migration.
- Fixed TypeScript errors in model providers and test creation.
- Fixed an issue where Jinja file filters returned JSON strings instead of Python objects.
- Fixed a test key mismatch in output_providers and results.
- Fixed an issue where `polyphemus_access` could be null in user settings.
- Fixed an issue where the websocket tests hung due to an incorrect message size limit.
- Fixed metric test data factories to include required `score_type` fields.
- Fixed an issue where the Markdown component crashed when endpoint responses contained JSON objects.
- Fixed an issue where `test_type_id` was overwritten on test update.
- Fixed an issue where `test_set_id` was present in the TestBase schema.
- Handled optional `prompt_id` in test components.

### Removed
- Removed the `[DEBUG]` prefix from API error logs.


## [0.6.6] - 2026-03-02

### Added
- Added explicit `min_turns` parameter for early stop control in tests.
- Added `min_turns` and `max_turns` support to import/export and synthesizer features.
- Added test association methods (`add_tests()`, `remove_tests()`) to the SDK's `TestSet` class for bulk test linking.
- Added client-side pagination to the metrics grid in the frontend.

### Changed
- Replaced the maximum turns input in the frontend with a turn configuration range slider, allowing users to set both `min_turns` and `max_turns`.
- Standardized naming: `max_iterations` has been renamed to `max_turns` across the backend, SDK, and documentation to reflect the actual semantics of conversation turns.
- Updated the frontend to use an 80% default for `min_turns` in the test detail slider, matching the backend/Penelope default when `min_turns` is not explicitly set.
- Improved turn budget awareness and deepening strategies in Penelope, ensuring every turn contributes substantive testing value.
- Refactored Penelope's orchestration to simplify the codebase and improve evaluator voice.

### Fixed
- Fixed an issue where the goal judge was creating spurious turn count criteria, leading to incorrect test failures.
- Fixed premature stopping issues in Penelope by decoupling goal-impossible conditions from `min_turns` and clarifying turn budget.
- Fixed a bug where metric updates could overwrite existing data with null values.
- Fixed focus loss and stale save button issues in the metric editor in the frontend.
- Fixed an issue where conversational metrics were not receiving the `conversation_history`, causing errors.
- Fixed metrics page pagination to show all backend type tabs, even with a large number of metrics.
- Fixed an issue where the conversational judge was incorrectly counting turns.
- Fixed an issue preventing early stopping before reaching `max_turns`.
- Fixed an issue where the push() method was discarding the backend response, leaving metric.id as None after creation.
- Fixed max-turns stop reason detection to check for "maximum turns" instead of the stale "max iterations" string.

### Removed
- Removed unnecessary indirection layers in Penelope's orchestration, simplifying the codebase.


## [0.6.5] - 2026-02-26

### Added
- Added core Polyphemus integration, including service delegation tokens, access control system with request/grant workflow, database migrations, Polyphemus-aware model resolution, and email notification template for access requests.
- Added frontend support for Polyphemus model access including access request modal and API route, model card UI states, Polyphemus provider icon and logo, and user settings interface with `is_verified` field.
- Added conversation-based tracing across SDK, backend, and frontend, linking multi-turn conversation interactions under a shared `trace_id` using a `conversation_id` field. This enables tracing entire conversations as a single logical unit.
- Added turn labels on edges and slider marks in graph view for conversation traces.
- Added a refresh button to trace filters.
- Added a full view button to the graph timeline.
- Added per-turn conversation I/O and first-turn trace linking to reconstruct multi-turn conversations from span data.
- Added resizable width to trace detail drawer.

### Changed
- Aligned backend defaults with SDK by using `rhesis/rhesis-default` instead of `vertex_ai/gemini-2.0-flash` for generation and evaluation models. Deployments can still override via `DEFAULT_GENERATION_MODEL` and `DEFAULT_EVALUATION_MODEL` environment variables.
- Improved traces UI with clickable responses and filter cleanup.
- Improved conversation detection and time formatting in traces UI.
- Improved traces UI with clickable responses and filter cleanup.
- Updated auth tests for PyJWT migration.
- Updated organization test to expect Polyphemus model creation.
- Replaced process-local conversation linking caches with a `ConversationLinkingCache` class backed by synchronous Redis (db 3), falling back to in-memory when Redis is unavailable.
- Generalized edge handle routing by direction in the trace graph view.

### Fixed
- Fixed OAuth callback URL host header poisoning. Rewrote `get_callback_url()` to never derive the callback URL from the untrusted HTTP Host header.
- Fixed Polyphemus configuration and clarified AI model configuration and default values.
- Fixed ConversationalJudge missing `id` attribute.
- Fixed security dependency vulnerabilities by updating dependencies like `cryptography`, `pillow`, `fastmcp`, `langchain-core`, `virtualenv`, and `mammoth`. Migrated from `python-jose` to `PyJWT`.
- Fixed fragile password redaction that broke when `SQLALCHEMY_DB_PASS` was unset.
- Fixed test config generation to use system default model.
- Fixed infinite loop in notification-dependent `useEffect` hooks.
- Fixed deduplication of traces by `trace_id` in list endpoint.
- Fixed bidirectional edges sharing connection points in trace graph view.
- Fixed missing `test_set_type` on creation and enforced type-matching assignment.
- Fixed the issue where the system default model was not being used for test config generation.
- Fixed the issue where the `ConversationalJudge` was missing the `id` attribute.
- Fixed the issue where the test set type was not being inferred correctly from imports.
- Fixed the issue where the `FROM_EMAIL` environment variable was being used for access review emails.
- Fixed the issue where the response model was not being restored on the settings endpoint.
- Fixed the issue where the token and comment tests were failing.
- Fixed the issue where the test config generation was not using the system default model.
- Fixed the issue where the test set type was not being added to the adaptive testing service and test data.

### Removed
- Removed `python-jose` dependency from worker and polyphemus.

### Security
- Addressed subgroup attack due to missing validation for SECT Curves by updating `cryptography` to >= 46.0.5 (CVE-2026-26007).
- Addressed out-of-bounds write on PSD images and write buffer overflow on BCn encoding by adding `pillow` >= 12.1.1 (CVE-2026-25990, CVE-2025-48379).
- Addressed DNS rebinding protection not enabled by default by updating `mcp` to >= 1.23.0 (CVE-2025-66416).
- Addressed RCE in "json" mode of JsonPlusSerializer by adding `langgraph-checkpoint` >= 3.0.0 (CVE-2025-64439).
- Replaced `python-jose[cryptography]` with `PyJWT>=2.10.0`, eliminating the transitive `ecdsa` dependency which has an unpatched Minerva timing attack vulnerability (CVE-2024-23342).
- Addressed DoS in Schema.load(many) by adding `marshmallow` >= 3.26.2 (CVE-2025-68480).
- Addressed TOCTOU vulnerabilities in directory creation by adding `virtualenv` >= 20.36.1 (CVE-2026-22702).
- Addressed directory traversal vulnerability by adding `mammoth` >= 1.11.0 (CVE-2025-11849).
- Addressed SSRF via image_url token counting by updating `langchain-core` to >= 1.2.11 (CVE-2026-26013).
- Redacted request/response body from Polyphemus provider logs to prevent leaking conversation content and PII.
- Redacted database and redis credentials from logs.


## [0.6.4] - 2026-02-18

### Added
- **Auto-Configure Endpoint Service:** Added AI-powered auto-configuration that analyzes reference material (curl commands, API docs) and generates Rhesis request/response mappings.
- **Test Explorer Feature:** Introduced a new "Test Explorer" page and layout for exploring test sets configured for adaptive testing.
- **Adaptive Testing API Endpoints and Service:** Re-added adaptive testing router with endpoints for listing adaptive test sets, fetching full tree, tests-only, and topics-only views.
- **Create Topic Endpoint and UI Button:** Added POST /adaptive_testing/{id}/topics endpoint that delegates to create_topic_node. Wire up an "Add Topic" dialog in the frontend tree panel so users can create topics from the UI.
- **Create Test Endpoint and UI:** Added POST /{id}/tests endpoint, create_test_node service, AddTestDialog frontend component.
- **Update Test Endpoint and Edit Dialog:** Added update_test_node service, PUT /{id}/tests/{test_id} endpoint, and EditTestDialog frontend component.
- **Delete Test Endpoint and Confirmation Dialog:** Added delete_test_node service, DELETE endpoint, and frontend delete button with confirmation dialog.
- **Update Topic Endpoint with Rename Support:** Added PUT /adaptive_testing/{id}/topics/{path} endpoint that renames a topic's current level name and cascades to all children and tests.
- **Create Adaptive Test Set Endpoint and UI:** Added endpoints and UI for creating adaptive test sets.
- **Generate Outputs Backend:** Added generate_outputs_for_tests service to invoke endpoint per test, and a POST generate-outputs route and request/response schemas.
- **Generate Outputs UI:** Added Generate outputs dialog with endpoint picker and submit flow.
- **Metric Selection Functionality:** Introduced metric selection functionality in AdaptiveTestingDetail component.

### Changed
- **Unified Model Environment Variables:** Consolidated model environment variables to a unified format (provider/model_name).
- **Standardized Terminology:** Consistently use 'language model' instead of 'llm model' and 'embedding model' instead of 'llm embedding model'.
- **Adaptive Testing:** Enhanced adaptive testing features with improved topic handling, test tree ID management, and validation methods.
- **Adaptive Testing:** Implemented drag-and-drop functionality to move tests between topics in the Test Explorer.
- **Adaptive Testing:** Implemented full CRUD operations for tests and topics in the Test Explorer.
- **Adaptive Testing:** Enhanced TestTree and generator integration with BaseLLM and LLMGenerator classes.
- **Adaptive Testing:** Updated TestTree to include topic markers in test sets.
- **Adaptive Testing:**  Enhanced output generation with concurrent endpoint invocations using asyncio.
- **Adaptive Testing:**  Migrated from requests to httpx for async support in RestEndpointInvoker.
- **Adaptive Testing:**  Use per-task db sessions in generate_outputs_for_tests.
- **Adaptive Testing:**  Allow adding test without topic.

### Fixed
- **Multi-Turn Metrics Evaluation:** Fixed issue where additional three-tier metrics were not evaluated during live multi-turn test execution.
- **Auto-Configure:** Resolved UnmappedClassError in tests and addressed PR review comments, including schema updates, SSRF protection, and auth token substitution.
- **Endpoint Creation:** Auto-assign active status on endpoint creation.
- **Duplicate Endpoint Naming:** Fixed duplicate endpoint naming to increment correctly (Copy) → (Copy 2) → (Copy 3).
- **Infinite Loop in useFormChangeDetection:** Removed initialData object reference from useEffect deps to prevent re-render loop.
- **Null Endpoint Statuses:** Set null endpoint statuses to active.
- **Test Explorer:** Filter tests by exact topic match only.
- **Adaptive Testing:** Fixed get_all_parents returning strings instead of TopicNodes.
- **Adaptive Testing:** Ensure InputLabel shrinks for topic selection in AdaptiveTestingDetail component.

### Removed
- **Test Explorer Feature:** Removed the original Test Explorer feature, replaced by the Adaptive Testing section.
- **Adaptive Testing:** Removed adaptive testing router, schemas, and service.
- **Adaptive Testing:** Removed profanity dependency from adaptive testing.


## [0.6.3] - 2026-02-12

### Added
- Added split-view playground and test creation from conversations, including endpoints, service layer, and frontend drawer with LLM-extracted pre-filled fields for both single-turn and multi-turn tests. (#1321)
- Added file import for test sets with multi-step API (analyze, parse, preview, confirm), supporting CSV, JSON, JSONL, and Excel formats with column mapping and user-friendly error handling. (#1319)
- Added server-side filtering to test sets grid with column filters for name, type, creator, and tags.
- Added rescore, last_run, and metric management to TestSet in SDK. (#1316)
- Added user-configurable embedding model settings, including a new API endpoint, user preferences, and utility functions. (#1297)
- Added output providers and re-scoring pipeline, including a rescore API endpoint and service. (#1311)
- Added last-run endpoint for retrieving the most recent completed test run summary. (#1311)
- Added native authentication system to replace Auth0, including email verification, password reset, and magic link. (#1283)
- Added multi-dimension embedding storage system with dedicated Embedding table and pgvector support. (#1237)
- Added development environment with hot reload support. (#1269)

### Changed
- Replaced Auth0 with native authentication system. (#1283)
- Replaced the default generation model from vertex_ai/gemini-2.0-flash to rhesis/default. (#1279)
- Enhanced test execution with mode and metrics parameters in SDK. (#1316)
- Enhanced embedding table with multi-dimension support and full-text search. (#1237)
- Improved error messages for model configuration and worker issues. (#1279)
- Improved Docker build resilience with apt-get retry logic. (#1277)
- Refactored authentication migrations to be idempotent and comprehensive. (#1283)
- Refactored SDK to use flat schema for batch generation and repack to nested. (#1315)
- Unified magic link as sign-in and sign-up flow. (#1283)
- Updated Docker images and tmpfs configurations in integration tests.
- Updated integration test configurations to use new ports for PostgreSQL and Redis.

### Fixed
- Enforced newline-separated steps in synthesizer instructions.
- Restored copy button on assistant messages.
- Passed test set type through file import flow.
- Added session ownership, thread safety, and limits to file import.
- Eliminated mapping UI flicker on auto-advance during file import.
- Aligned tests with bulk_create_tests return type.
- Handled optional dimension and demographic in create_prompt.
- Resolved pytest warnings in SDK test suite. (#1316)
- Addressed code review issues in execution pipeline. (#1316)
- Corrected mirror.gcr.io image paths for postgres and redis. (#1277)
- Fixed table name and query in migration email script. (#1283)
- Fixed open redirect via exact domain validation in authentication. (#1283)
- Fixed bulk test creation performance for large garak imports. (#1272)
- Fixed the issue where re-score retries were silently falling back to live execution. (#1316)
- Fixed the issue of raising AttributeError when TestRuns.pull returns None. (#1316)
- Fixed the issue of parameter shadowing in rescore_test_run. (#1316)
- Fixed the issue of deprecated datetime.utcnow() with datetime.now(timezone.utc) in output providers. (#1316)
- Fixed the issue of reusing shared APIClient in _resolve_metrics instead of per-call instantiation. (#1316)
- Fixed the issue of using valid UUIDs for TestResultOutput construction. (#1316)
- Fixed the issue of importing statements and mock patch paths. (#1297)
- Fixed the issue of alembic downgrade migration. (#1310)
- Fixed the issue of multiple head revisions in alembic migration files. (#1237)
- Fixed the issue of using server_default and add nano_id unique index. (#1237)
- Fixed the issue of uselist=True to embeddings relationships. (#1237)
- Fixed the issue of adding Embedding EntityType to migration. (#1237)
- Fixed the issue of BetterTransformer optimization and upgrade to CUDA base image. (#1279)
- Fixed the issue of uv.lock to include optimum package dependencies. (#1279)
- Fixed the issue of validating generation model and improve error messages for test config and MCP. (#1279)
- Fixed the issue of including actual error details in API error responses. (#1279)
- Fixed the issue of preventing rh delete from removing manually created containers. (#1279)
- Fixed the issue of clearing validation warnings when models are no longer defaults. (#1279)
- Fixed the issue of updating assertion to match detailed error messages. (#1279)
- Fixed the issue of adding default uvicorn start for docker/integration tests. (#1273)
- Fixed the issue of moving test-set associations outside the loop to fix O(n²) behavior. (#1272)
- Fixed the issue of caching Status and TypeLookup entities during bulk operations. (#1272)

### Removed
- Removed Auth0 dependency. (#1283)
- Removed embedding dimensions from user settings. (#1297)
- Removed local-style backend test workflow file.


## [0.6.2] - 2026-02-05

### Added
- Added a Playground for interactive endpoint chat via WebSocket, accessible under the Testing section. This includes:
    - Real-time WebSocket communication for conversational endpoint testing.
    - Chat message handling (CHAT_MESSAGE, CHAT_RESPONSE, CHAT_ERROR).
    - `usePlaygroundChat` hook for managing chat state and conversation IDs.
    - TraceDrawer integration for viewing endpoint response traces.
    - Trace linking from assistant message bubbles to trace details.
    - A "Playground" button on the endpoint detail page to pre-select the endpoint in the Playground.
    - Markdown rendering in playground chat bubbles.
    - Copy button to playground message bubbles.
- Added Jira ticket creation from tasks via MCP integration.
- Added display of creation dates for tests and test sets in the UI.
- Added `./rh dev` command for local development setup, including commands for starting and managing backend, frontend, chatbot, docs, worker, and polyphemus services.
- Added `lm-format-enforcer` as a new provider.

### Changed
- Increased SDK function timeout from 30s to 120s (configurable via `SDK_FUNCTION_TIMEOUT` env var).
- Increased SDK connector ping interval/timeout defaults (60s/30s) with `RHESIS_PING_INTERVAL` and `RHESIS_PING_TIMEOUT` env vars.
- Standardized `session_id` as the canonical name for conversation tracking in the chat handler.
- Enhanced WebSocket retry mechanism for robustness, including increased reconnect attempts, a max reconnect delay cap, a manual reconnect method, and page visibility detection for reconnecting.
- Made Jira space selection optional at tool creation.
- Enforced required metadata for GitHub and Jira tool connections.
- Improved local development commands and help output for `./rh dev`.

### Fixed
- Fixed Redis URL configuration to check `BROKER_URL` first for consistency.
- Reduced Redis reconnection log noise by using DEBUG level.
- Fixed WebSocket ping timeouts by running synchronous endpoint functions in a thread pool.
- Fixed context variable propagation to worker threads for trace linking.
- Fixed connector test isolation issues.
- Fixed soft delete filtering in connector services by using QueryBuilder.
- Fixed issue where only sessionId was reset when switching endpoints in the Playground; now all state is cleared.
- Fixed client method to create-ticket-from-task service.
- Fixed issue where users could not execute test configs from other users within the same organization.
- Updated chat handler tests to use `session_id`.

### Removed
- Removed unused `mcp_connect` file.

### Security
- Upgraded protobuf to >=6.33.5 (fixes CVE-2026-0994: JSON recursion depth bypass).
- Upgraded python-multipart to >=0.0.22 (fixes CVE-2026-24486: arbitrary file write).


## [0.6.1] - 2026-01-29

### Added

- Integrated Garak LLM vulnerability scanner for automated security testing. Features include GarakDetectorMetric for evaluating responses using Garak detectors, GarakProbeService for enumerating probes with taxonomy mapping, import UI with probe selection, test set to metric association table, and 12 built-in detector metrics (MitigationBypass, Continuation, Toxicity, etc.). Supports multi-strategy dynamic prompt extraction for comprehensive probe coverage. (#1190)
- Added two-level Redis caching (memory L1 + Redis L2) for Garak probe enumeration with background pre-warming on startup for instant API responses. Includes graceful degradation when Redis is unavailable. (#1202)
- Implemented 3-level metrics hierarchy for test execution. Execution-time metrics now override test set and behavior metrics, with MetricsSource enum (behavior, test_set, execution_time) for tracking. Added RerunTestRunDrawer component for re-running tests with metric source selection. (#1206)
- Added separate MCP Jira and Confluence provider integrations with stdio transport support, replacing the combined Atlassian provider. Each provider has dedicated credential fields for URL, username/email, and API token. (#1197)
- Added MCP GitHub repository retrieval with repository scope configuration, URL import tab for direct links, and provider-agnostic support for importing resources from URLs. (#1148)
- Added MCP observability with ObservableMCPAgent featuring OpenTelemetry tracing, dynamic agent selection based on RhesisClient availability, and @endpoint decorator support for MCP service functions. Includes DisabledClient pattern for environments without observability credentials. (#1102)
- Added context and expected response fields to test run detail view, displaying context array as bullet points and expected response in the test result overview tab. (#1201)
- Added Model entity with provider auto-resolution (accepts provider name string instead of UUID), user settings management for default models, and get_model_instance() for converting to BaseLLM. Includes ModelRead schema to exclude sensitive API keys from responses. (#1132)

### Changed

- Refactored metrics context validation to SDK. Metrics requiring context now return visible failure results with unified error messages instead of being silently skipped. (#1200)
- Upgraded FastAPI and Starlette to latest versions. (#1175)
- Upgraded security-related dependencies to address vulnerabilities. (#1174)
- Refactored telemetry infrastructure for improved observability. (#1125)

### Fixed

- Fixed migration CardinalityViolation error by using IN instead of = for multi-row subquery in type_lookup table queries. (#1207)
- Added Rust build dependencies to Dockerfile.dev for garak's base2048 dependency compilation. (#1198)
- Optimized Docker image by using CPU-only PyTorch, removing ~2.8GB of CUDA/nvidia packages. Image size reduced from 3.38GB to 2.60GB with Garak support. (#1196)
- Fixed connector disabled state handling with RHESIS_CONNECTOR_DISABLE environment variable support. Backend and chatbot now default to DisabledClient when project_id is not set. (#1168)
- Separated API client from observability client to fix initialization issues. RhesisClient.from_environment() now gracefully falls back to DisabledClient when credentials are missing. (#1155)
- Fixed backend test cleanup by combining all database operations into a single transaction and adding proper asyncio.CancelledError handling in ConnectionManager. (#1142)
- Updated langchain-core to 1.2.5 and urllib3 to 2.6.3 to address security vulnerabilities. (#1160)
- Updated aiohttp to fix compatibility issues. (#1164)
- Updated various packages to fix issues. (#1162)

### Removed

- Removed legacy document upload system in favor of source-based architecture. Updated tests to use file instead of deprecated document parameters. (#1169)



## [0.6.0] - 2026-01-15

### Added
- Added comprehensive OpenTelemetry integration for enhanced observability, including traces, filtering, and visualization in the UI.
- Added Chatbot Intent Recognition feature.
- Added Github MCP Provider.

### Changed
- Improved MCP connection stability and added multi-transport support.
- Integrated test execution into the organization onboarding process.
- Improved Dockerfile.dev for faster builds with better layer caching and dependency installation.

### Fixed
- Resolved Cloud Run deployment issues related to port configuration, image caching, and UV detection.


## [0.5.4] - 2025-12-18

### Added
- Added a new Polyphemus provider with schema support. This allows users to connect to and interact with Polyphemus data sources, leveraging schema information for improved data handling and validation. (#1046)


## [0.5.3] - 2025-12-11

### Added
- Added unique constraint to `nano_id` columns in the database.
- Added endpoint test functionality for connection testing.
- Added multi-turn test support in manual test writer.

### Fixed
- Fixed MCP authentication errors and improved related UX.
- Improved MCP error handling and reporting.
- Separated execution status from test results in notification emails.

### Changed
- Improved MCP usability.


## [0.5.2] - 2025-12-08

### Changed

- fix(dashboard): remove invalid fields from activities response (#1017)
- fix: remove permission restrictions from entity routes (#1015)
- Add Test Connection Tool (#971)



## [0.5.1] - 2025-12-04

### Added
- Modernized dashboard with MUI X charts and activity timeline.
- Added support for OpenRouter provider.
- Added "Is Verified" field to user profiles.

### Changed
- Increased exporter timeout from 10 to 30 seconds.
- Optimized Dockerfile build and added uv link mode for faster development.

### Fixed
- Fixed connector output mapping to properly support message fields.
- Fixed issues with backend execution RPC and improved UI.
- Fixed metric creation to support both SDK and frontend approaches with proper field handling.


## [0.5.0] - 2025-11-27

### Added
- Added Tool Source Type to allow specifying the origin of tools.
- Added bidirectional SDK connector with intelligent auto-mapping for seamless integration.
- Added in-place test execution without worker infrastructure for faster testing.
- Added database persistence for onboarding progress.

### Changed
- Implemented multi-turn conversation preview and improved generation flow for better user experience.
- Implemented comprehensive multi-turn test support, including creation, listing, and execution.
- Improved synthesizers for enhanced performance and functionality.
- Refactored Base Entity for improved code structure and maintainability.
- Updated MCP Tool Database for enhanced data management.
- Implemented Tool Configuration Frontend for easier tool management.
- Updated test generation endpoint for multi-turn tests.
- Updated Models List for Providers.

### Fixed
- Fixed template rendering issues.
- Fixed multi-turn test generation response format.
- Fixed migration backend tests.
- Fixed MCP Tool arguments.
- Fixed logging and error messages in routes/services for improved debugging.
- Fixed Docker Compose configuration for production readiness.
- Fixed multi-turn test creation and listing issues.
- Fixed incorrect columns in test set download.
- Fixed test failures and improved schema design.
- Fixed SDK tests.
- Fixed generate test config endpoint.
- Fixed telemetry deployment issues.
- Fixed: Remove Logout Button In Local.


## [0.4.3] - 2025-11-17

### Added
- Implemented centralized conversation tracking for multi-turn conversations. This allows for improved context management and more seamless user experiences in conversational flows. (#856)


## [0.4.2] - 2025-11-13

### Added
- Added support for multi-turn tests, including configuration validation, max turns slider (1-50 range), and test type detection.
- Added 5 Rhesis conversational metrics with database migration.
- Added 6 conversational metrics to initial data.
- Added tags and comments infrastructure for sources.
- Added scenarios feature.
- Added generic MCP (Model Control Plane) integration endpoints, including user model configuration and a general query endpoint.
- Added `metric_scope` field to support single-turn/multi-turn test applicability.
- Added a procedure to delete user and organization data.
- Added local development setup with Docker Compose and enhanced command-line interface.
- Added environment-based URL configuration.

### Changed
- Refactored test executors using the Strategy Pattern.
- Refactored local initialization functions and updated API token.
- Refactored MCP service to use `MCPAgent`'s `Union[str, BaseLLM]` support.
- Refactored MCP prompts to Jinja2 templates.
- Implemented settings caching and auto-persistence.
- Simplified multi-turn test executor to preserve Penelope trace as-is.
- Updated email sender name format for SendGrid SMTP.

### Fixed
- Improved multi-turn test metrics serialization and frontend display.
- Resolved Penelope dependency path issues in Docker builds.
- Restored backward compatibility imports in `test_execution.py`.
- Resolved remaining test failures.
- Resolved dataclass serialization error with documents.
- Ensured context headers are forwarded and added secure auth token field.
- Fixed welcome email recipient by adding configurable regex patterns for exclusions.
- Sanitized auth tokens and headers in logs.
- Fixed an issue where `user_id` was not being passed to `crud.get_endpoint` in `BackendEndpointTarget`.

### Removed
- Removed `Mixed` test set type.


## [0.4.1] - 2025-10-30

### Added
- Added SDK metrics sync utility and migration to synchronize metrics data with the SDK.
- Added iteration context support to test generation, allowing for more context-aware test creation.
- Added telemetry instrumentation with detailed documentation and security measures using OpenTelemetry.
- Added Alembic migration for merging telemetry and Rhesis models.
- Added source ID tracking to tests generated from documents.
- Added Error status for test results without metrics.
- Added founder welcome email for new user sign-ups.
- Added optional test set name parameter for test generation.
- Added default Rhesis model to all existing organizations and set it as default for new users.
- Added `is_protected` field to Model schema to prevent editing/deletion of system models.
- Added cascade-aware restoration service for soft-deleted entities.
- Added API key authentication with user-based rate limiting.
- Added Insurance Chatbot endpoint to initial data load.
- Added execution errors display to email notifications.
- Added source-specific statuses to migration.
- Added global 404 and 410 error handling with restore functionality.
- Added API to return HTTP 410 for soft-deleted entities.

### Changed
- Improved metric evaluation concurrency with retry and timeout handling.
- Improved welcome email template.
- Improved AI-based test generation with enhanced UI and backend support.
- Improved test configuration generation with project context and database integration.
- Enhanced user activity tracking with telemetry integration.
- Enhanced task operations with telemetry tracking.
- Replaced document uploads with `source_ids` in test generation.
- Renamed provider types 'together' to 'together_ai' and 'meta' to 'meta_llama'.
- Refactored metrics adapter to use SDK MetricFactory directly and simplify the integration.
- Refactored sources to replace `include` parameter with dedicated endpoint for content.
- Updated Rhesis model naming and descriptions.
- Updated supported file types for source extraction.
- Updated email notifications to display accurate execution time.
- Updated /generate/content endpoint to Vertex AI.
- Updated test configuration generation to clarify behavior selection.
- Updated Source schema to match model structure.
- Updated user settings update logic in database migrations.
- Updated telemetry instrumentation with metadata sanitization.
- Updated ScoreEvaluator to use passing_categories instead of reference_score.
- Updated prepare_metric_configs to accept Metric models.
- Updated evaluator to accept Metric models directly, eliminating conversion layer.
- Updated user and organization ID handling in analytics tables.
- Updated telemetry middleware to clean up whitespace.
- Updated database credentials in documentation.
- Updated migration order to follow main branch migrations.
- Updated SDK to support both plain and OpenAI-wrapped JSON schemas.
- Updated Rhesis model as default for users without configured defaults.
- Updated Rhesis SVG logo for default model icon.
- Updated source_ids from UUID list to SourceData objects.
- Updated source_metadata to remove uploader and timestamp duplication.

### Fixed
- Fixed line length and unused variable linting issues.
- Fixed Docker cache from staling migration files.
- Fixed type lookup descriptions.
- Fixed path collision with alembic package.
- Fixed whitespace in telemetry middleware.
- Fixed config generator to accept user defined model.
- Fixed OAuth session persistence in local development.
- Fixed failing tests and refactored to use fixtures over mocks.
- Fixed tasks referencing statuses during rollback_initial_data.
- Fixed custom title not overriding filename in source upload.
- Fixed auth function.
- Fixed endpoint project reference to match renamed project.
- Fixed critical bugs in endpoint processing and chatbot deployment.
- Fixed email test results inconsistency.
- Fixed pydantic v2 deprecation warning.
- Fixed use of proper db session in recycle endpoints.
- Fixed missing comments relationship to User model.
- Fixed duplicate source_id column from test table.
- Fixed tasks referencing statuses during rollback_initial_data.
- Fixed handle tasks referencing statuses during rollback_initial_data.
- Fixed handle categorical metrics in SDK adapter and legacy tests.
- Fixed security vulnerabilities in metric test functions.
- Fixed security vulnerabilities in recycle endpoints.
- Fixed security vulnerability where password was not redacted from SMTP config logs.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where auth_type was not set if auth_token was not successfully loaded.
- Fixed security vulnerability where normalized email attribute was not used instead of deprecated email.
- Fixed security vulnerability where protected model updates were not allowed when values didn't change.
- Fixed security vulnerability where protected system models were not prevented from being edited.
- Fixed security vulnerability where protected system models were not prevented from being deleted.
- Fixed security vulnerability where organization filtering was not enforced in metric test functions.
- Fixed security vulnerability where OAuth session was not persisted in local development.
- Fixed security vulnerability where organization_id query parameters were not removed from recycle endpoints.
- Fixed security vulnerability where


## [0.4.0] - 2025-10-16

### Added
- Added support for user-defined LLM provider generation and execution.
- Added metric-specific model configuration.
- Added user settings API endpoints for managing models.
- Added API endpoints for test review manipulation.
- Added a sample size parameter to test configurations.
- Added recycle bin management endpoints for soft-deleted items.
- Added leave organization feature.
- Added support for re-inviting users who left organizations.
- Added individual test stats endpoint.
- Added document upload, extract, and content endpoints.
- Added uploader name to source metadata.
- Added SourceType enum to source schema and initial data.
- Added test connection button to model dialog.
- Implemented encryption for sensitive data in Model and Token tables, and Endpoint model authentication fields.

### Changed
- Refactored source handling to be completely dynamic using a handler factory pattern.
- Refactored storage to implement hybrid cloud/local storage lookup.
- Refactored model connection test to a dedicated service and model router.
- Centralized user settings with a manager class and renamed `llm` to `models`.
- Enhanced test configuration generation and schema.
- Updated CRUD utilities for soft deletion.
- Enhanced QueryBuilder with soft delete methods.
- Updated DocumentHandler for persistent storage.
- Renamed 'google' provider to 'gemini' for consistency.
- Separated dev and staging databases.

### Fixed
- Corrected test count calculation in execution summary.
- Corrected deepeval context relevancy class name.
- Resolved DB scope issue in `execute_single_test` exception handler.
- Resolved JSON serialization error with dedicated model fetcher.
- Resolved soft delete filtering and test issues.
- Resolved ValueError in document upload endpoint.
- Resolved upload endpoint authentication and database session issues.
- Improved DocumentHandler validation and MIME type support.
- Fixed GCS initialization by removing JSON corruption.
- Fixed handling of base64-encoded service account keys.
- Fixed unicode filenames in content disposition header.
- Ensured consistent whitespace stripping in endpoint validators.
- Properly handled null endpoint values in test connection schema.
- Properly persisted user settings with UUID serialization.
- Implemented soft delete to resolve 500 error on user removal.
- Enabled tags, tasks, and comments for test results.
- Fixed organization filtering and accurate token count.
- Properly filtered soft-deleted records in raw queries with `.first()`.

### Removed
- Removed frontend comment functionality from sources.
- Removed editor settings from user settings.
- Removed obsolete comment about deprecated functions.
- Removed SDK configuration and added model parameter for test generation.


## [0.3.0] - 2025-10-02

### Added
- Added support for persistent file storage using a new `StorageService` for multi-environment file handling.
- Added a new API endpoint for generating test configurations.
- Added `Source` entity type support to the comments system, including model and schema updates.
- Added versioning information for both backend and frontend components.
- Added a demo route with Auth0 login_hint integration.

### Changed
- Refactored the database session management to use `get_tenant_db_session` for improved Row-Level Security (RLS) and tenant context handling.
- Refactored all routes to use proper database sessions and tenant context.
- Refactored CRUD functions to include tenant context support.
- Updated document endpoints for persistent storage.
- Optimized the `with_count_header` decorator for better performance and compatibility with different dependency patterns.
- Improved DocumentHandler validation and MIME type support.
- Updated the Source model and schema with comments support.
- Updated assign_tag and remove_tag to require organization_id and user_id.
- Updated test set service to regenerate attributes on test set update.
- Enhanced mixin structure for comment and task relationships.
- Streamlined task retrieval and comment counting.
- Implemented task management features and email notifications.

### Fixed
- Fixed critical cross-tenant data access vulnerabilities by implementing query-level organization filtering middleware.
- Fixed numerous CRUD and StatsCalculator vulnerabilities related to organization filtering.
- Fixed missing `organization_id` and `user_id` parameters in various CRUD operations, tasks, and API endpoints.
- Fixed transaction management issues and improved CRUD utilities.
- Fixed 'Not authenticated' error in auth/callback route.
- Fixed Pydantic schema field shadowing and enum serialization warnings.
- Fixed UUID validation issues in organization filtering.
- Fixed CORS staging restrictions.
- Fixed test failures with RLS and status fixtures.
- Fixed API key generation to return the actual token value.
- Fixed issues with initial data loading and organization filter warnings.
- Fixed chord callback failures due to missing tenant context.
- Fixed model relationships for comments.
- Fixed organization filtering warnings in test set execution.
- Corrected delete_organization CRUD function and router.

### Removed
- Removed manual transaction management in backend methods.
- Removed legacy `set_tenant` functions and unused query helpers.
- Removed verbose debug logging statements.


## [0.2.4] - 2025-09-18

### Added
- Added task management functionality, including task creation, assignment, status tracking, and comment count.
- Added document sources to test set attributes.
- Added `test_metadata` column for document source tracking in test sets.
- Added metadata field to `TestSetBulkCreate` schema.
- Added support for tags, prompt templates, response patterns, sources, and statuses in backend testing.
- Added Alembic SQL Template System for database migrations.
- Added task statuses and priorities to the database.
- Added task assignment email notifications.
- Integrated DocumentSynthesizer for document-based test generation and auto-selected it in the task system.
- Added migration script for merging task and metadata revisions.

### Changed
- Refactored task model and management logic.
- Updated backend to use SDK Document dataclass.
- Optimized test patterns and fixed websockets deprecation warnings.
- Refactored database exceptions for CRUD routes.
- Refactored all routes to use improved database session handling.
- Enhanced task management with comment count and completion tracking.
- Updated backend schema to accept arrays in `test_metadata` instead of strings.
- Updated backend to use LLM service and promptsynth accepting models.
- Auto-populated `creator_id` in task creation and updated `TaskCreate` schema.
- Implemented organization-level validation for task assignments.

### Fixed
- Fixed model selection logic.
- Fixed route behavior for metric, model, and organization.
- Fixed comment and token frontend interface compatibility with the backend.
- Fixed bulk test set metadata format in API docs.
- Fixed an issue where the documents parameter was not properly passed to the task system.
- Fixed Python package version conflicts.

### Removed
- Removed unnecessary column alterations in the task model migration script.
- Removed metrics from the backend (moved to SDK).


## [0.2.3] - 2025-09-04

### Added
- Added a new endpoint to retrieve test run statistics, providing insights into test execution data.
- Implemented comment support with CRUD operations and API endpoints, including emoji reactions.
- Added `?include=metrics` query parameter to the behaviors endpoint to include related metrics.
- Added `created_at` and `updated_at` fields to relevant entities for tracking purposes.

### Changed
- Refactored common utilities for statistics calculation, improving code maintainability.
- Updated environment variable handling for improved local development and deployment flexibility.
- Replaced `response_format` argument with `schema` in content generation functionality for clarity.
- Migrated linting process to `uvx` for improved performance and consistency.
- Updated Docker configuration and scripts for streamlined deployment.

### Fixed
- Fixed an issue causing slow loading times on the metrics confirmation page during creation.
- Made the `name` field optional when editing metrics.
- Resolved an issue preventing migrations from running when a revision already exists.
- Fixed macOS IPv6 localhost connection issues.
- Removed user-level permission check from the test run download endpoint.
- Corrected routes formatting for improved API consistency.


## [0.2.2] - 2025-08-22

### Added
- Added Redis authentication for enhanced security.
- Added a new endpoint for document content extraction (`/documents/generate`).
- Added document support to the `/test-sets/generate` endpoint.
- Added unit tests for backend components, in particular routes.
- Introduce CI/CD pipeline for testing, including codecov integration.

### Changed
- Updated Docker configuration and requirements.
- Refactored Docker Compose and environment configuration for improved maintainability.
- Improved migration and startup scripts for Docker backend.
- Updated backend dependencies for markitdown migration to include docx, pptx, and xlsx formats.
- Reduced the default Gunicorn timeout from 5 minutes to 1 minute.
- Standardized backend routes for UUID validation and foreign key error handling.
- Improved consistency for demographic routers.
- Updated dimension entity in models and routing.
- Improved database configuration for testing.
- Updated `start.sh` to use `uv run` for Uvicorn.

### Fixed
- Fixed Dockerfile to handle new SDK relative path.
- Corrected SDK path in backend `pyproject.toml`.
- Fixed foreign key violation errors.
- Fixed field label naming issue.
- Adjusted handling of UUIDs for topic routes.
- Fixed syntax error in document generation endpoint.
- Fixed issue where PDF extraction was causing 503 errors by increasing Gunicorn timeout.


## [0.2.1] - 2025-08-08

### Added
- Added support for filtering test sets related to runs.
- Added the ability to upload documents via the `/documents/upload` endpoint.
- Added optional `documents` argument to the `/generate/tests` endpoint, allowing test generation based on provided documents.
- Added response model and improved documentation for the `/documents/upload` endpoint.
- Added router support for test result statistics.
- Added new schema definition for test results.
- Added "last login" functionality to user login.

### Changed
- Improved Document validation error messages.
- Refactored the stats module to accommodate specifics of test results.
- Refactored `test_results.py` to `test_result.py` for naming consistency and modularized the code.
- Improved terminology consistency in document handling.
- Updated contributing guides with PR update and creation functionalities, and macOS specificities.

### Fixed
- Fixed an issue where `None` documents were not handled correctly in the `/generate/tests` endpoint.
- Fixed missing imports and migrated Document validator to Pydantic v2.
- Fixed a GUID import path issue in Alembic migrations.
- Fixed an issue ensuring all authenticated users via Auth0 have their `auth0_id` field populated.
- Fixed Unix socket path.

### Removed
- Removed the standalone stats module.


## [0.2.0] - 2025-07-25

### Added
- Introduced an email-based notification system for test run completion.
- Implemented sequential test execution functionality.
- Added configuration options (execution mode) to test sets.
- Added a download button to test runs for downloading results.
- Introduced the "Invite Team Member" step in the user onboarding process.
- Implemented rate limiting (10 invites/hour) and max team size (10) for team invitations.
- Added start-up scripts for convenience.
- Enabled Gemini as a backend for Rhesis metrics.
- Added debugging script for metrics.

### Changed
- Improved team invitation security and validation, including email uniqueness checks and proper email validation.
- Enhanced error handling and duplicate detection for team invitations, providing better UX with specific validation messages.
- Refactored the task orchestration and results collection processes.
- Moved worker infrastructure to Redis for improved performance and scalability.
- Adjusted score computation to use raw scores instead of normalized scores.
- Updated documentation for OData filtering.
- Updated backend documentation.
- JWT expiration now guarantees backend session expiration.
- Logout and session expirations now redirect to the home page.
- Improved UUID handling for test bulk creation.
- Adjusted email notification header.

### Fixed
- Fixed validation issues in OData filtering.
- Fixed issues with test set execution.
- Fixed test set download functionality.
- Fixed missing expected response in reliability prompts.
- Fixed the score result for binary and categorical metrics.
- Fixed WebSocket implementation.
- Fixed issue with Google Mirascope provider.
- Fixed handling of tokens with no expiration.
- Fixed backend handling of null values for GUIDs and UUIDs.
- Fixed test set execution via test run list.
- Fixed output mapping for test execution.
- Fixed status calculation.
- Fixed multiple logging entries.
- Fixed issue where objects would expire during after commit.


## [0.1.0] - 2025-05-15

### Added
- Initial release of the backend API
- Core database models and schemas
- Authentication system with JWT
- Basic CRUD operations for main entities
- API documentation with Swagger/OpenAPI
- Integration with PostgreSQL database
- Error handling middleware
- Logging configuration

### Note
- This component is part of the repository-wide v0.1.0 release
- After this initial release, the backend will follow its own versioning lifecycle with backend-vX.Y.Z tags

[Unreleased]: https://github.com/rhesis-ai/rhesis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/v0.1.0 
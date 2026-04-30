# SDK Changelog

> **Migration Notice:** As of May 2025, this SDK has been migrated from its own repository 
> (https://github.com/rhesis-ai/rhesis-sdk) into the Rhesis main repo 
> (https://github.com/rhesis-ai/rhesis). All releases up to v0.1.8 were made in the original repository.
> While the SDK is at version 0.1.8 internally, it's included in the repository-wide v0.1.0 release tag
> for the initial release. After this, the SDK will continue with its own versioning using sdk-vX.Y.Z tags.

All notable changes to the Rhesis SDK will be documented in this file.

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
- Fix LiteLLM proxy strict JSON schema for structured output (#1659)

* fix(sdk): use litellm helper for strict json schema

LiteLLMProxy now builds response_format via type_to_response_format_param so Azure/OpenAI strict mode gets additionalProperties:false on all object nodes (issue #1657).

Adds a regression test for nested Pydantic models.

* refactor(sdk): streamline response_format assignment in LiteLLMProxy

Consolidate the assignment of the response_format parameter in LiteLLMProxy to a single line for improved readability and maintainability.
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



## [0.6.12] - 2026-04-09

### Added
- Introduced a lightweight `rhesis-telemetry` package to serve as a foundation for telemetry.
- Added a built-in "echo" use case to the chatbot that returns user input verbatim without invoking an LLM or consuming rate limits.
- Added a POST `/test_runs/{id}/cancel` endpoint to cancel running tests.
- Implemented a "Cancel Test Run(s)" button in the frontend to allow users to cancel queued or in-progress test runs.
- Implemented mid-flight cancellation of tests via an asyncio watchdog, allowing tests to be cancelled while running.
- Added user feedback functionality for suggestion generation in adaptive testing.
- Exposed per-metric evaluation details in the backend.
- Added optional metrics on tree nodes in the SDK.
- Implemented a mop-up pass to retry transient failures after the main batch of tests.

### Changed
- Repurposed the `rhesis` meta-package as a lightweight telemetry foundation.
- Replaced chord fan-out with an async batch execution engine for improved performance.
- Switched the Celery worker from a prefork pool to a threads pool to eliminate fork-related crashes.
- Invokers, the endpoint service, and metrics now support asynchronous operations.
- The default sort order for test retrieval in adaptive testing is now descending, prioritizing the most recent tests.
- Adaptive testing now defaults to overwriting existing outputs when generating evaluations.
- Increased the default per-test timeout from 300s to 1800s (30 minutes).

### Fixed
- Fixed unique ordered model IDs in LiteLLM listings.
- Fixed SIGTRAP/SIGKILL during concurrent Vertex AI tests by passing credentials directly.
- Fixed a stuck "Progress" status on TestRun by catching Celery task failure and task revoked signals.
- Fixed bugs in the batch engine and invoker layer, including misplaced docstrings and thread-safety races.
- Prevented negative duration on failed test runs in the frontend.
- Disabled raw HTML parsing in markdown to prevent React errors.
- Bound telemetry tasks to the Redis Celery app to prevent broker unavailability issues.
- Restored `timeout_error` and `connection_error` to `_TRANSIENT_ERROR_TYPES`.
- Improved telemetry ingestion error logging with stage tracking and tracebacks.
- Restored backward-compatible API and fixed broken tests in invokers.
- Fixed an RPC close bug and eliminated per-invocation object construction for performance improvements.
- Persisted error records for failed tests.
- Fixed lazy loading of metrics, services, models, and synthesizers in the SDK.

### Removed
- Removed the option to overwrite existing outputs in adaptive testing, defaulting to true.


## [0.6.11] - 2026-03-26

### Added
- Added `TokenChunker`, `SentenceChunker`, and `RecursiveChunker` classes, backed by the `chonkie` library, for enhanced text chunking capabilities.
- Added `chonkie` as an explicit SDK dependency.

### Changed
- Replaced the custom chunker implementation with `chonkie`-backed strategies for improved performance and flexibility.
- Replaced instances of the deprecated `SemanticChunker` with `RecursiveChunker` in `synthesizers/base.py` and `examples/config-synthesizer.ipynb`.
- Removed strict input validation from base judge to support conversational trace metrics evaluation.

### Fixed
- Fixed an issue where long-running test executions could block the main WebSocket listener loop, leading to connection drops. Test and metric executions are now non-blocking.
- Fixed Pyright typing errors related to async callback signatures in `WebSocketConnection`.
- **Security**: Pinned the `litellm` dependency to version `<=1.82.3` due to compromised versions after 1.82.3.

### Removed
- Deprecated the custom-written `SemanticChunker` class. Consider using `RecursiveChunker` or the `SemanticChunker` provided by the `chonkie` library.

## [0.6.10] - 2026-03-23

### Added
- Added `TestRuns.stats()` and `TestResults.stats()` collection methods with typed Pydantic response models and optional pandas DataFrame conversion.
- Added NIST-aligned password hardening with zxcvbn strength scoring, context-specific word blocking, and HaveIBeenPwned breach checks. Minimum password length raised to 12 characters.

### Changed
- Made SDK metrics evaluation async-first, enhancing performance and aligning with the async-first architecture of the SDK.
- Refactored MetricEvaluator to use a strategy pattern for backend metric evaluation, improving flexibility and maintainability.
- Exposed `format_conversation()` as a stable public API and improved handling of tool-call-only assistant messages.
- Updated RhesisLLM to utilize a shared aiohttp.ClientSession for concurrent batch requests, enhancing performance through connection pooling.

### Fixed
- Fixed test run stats display by using `metadata.total_test_runs` for empty-state check.
- Fixed backend issue where `status_breakdown` was incorrectly required in the `TestRunTimelineData` schema.
- Fixed backend issue where `result_distribution` was classifying test runs by execution status instead of actual test outcomes.
- Fixed frontend issue where `FRONTEND_ENV` was not exposed to client-side code.
- Fixed backend issue where the package version was falling back to 0.1.0 due to missing `pyproject.toml` in the runtime image.
- Fixed onboarding `StaleDataError` caused by RLS session variable loss after `db.commit()`.
- Fixed test run advanced filters to only show metrics used in the current test run.
- Fixed tests grid random reordering by adding a stable secondary sort.
- Fixed counts including soft-deleted records.
- Fixed MCP auth to use the system default model and fixed credential testing for HTTP providers.
- Fixed Notion integration link to internal integrations page.
- Fixed frontend issue where tasks created from the single-turn test result drawer did not store `test_run_id` in task_metadata.
- Fixed frontend issue avoiding unsafe UUID cast for optional user_id.

### Removed
- Removed `lm-format-enforcer` dependency due to incompatibility with `transformers>=5.0.0`.
- Removed ToxicCommentModel and replaced it with PerspectiveToxicity.


## [0.6.9] - 2026-03-12

### Added
- Added per-turn retrieval context (RAG sources) separate from metadata in conversational metrics.
- Added `tool_calls` as a Rhesis-controlled field to the evaluation pipeline, flowing from endpoint response mapping through Penelope conversation turns, backend evaluation, SDK metric judges, DeepEval adapter, and Jinja2 prompt templates.
- Added batch processing capability to the RhesisLLM class by implementing the `generate_batch` method.
- Added per-turn metadata to conversational metrics, allowing each turn of a Penelope conversation to carry endpoint metadata through the full evaluation pipeline.
- Implemented batch size reduction and retry mechanism to synthesizer.
- Added explicit `a_generate` to sync-only LLM providers.
- Added `close_background_loop` for async_utils cleanup.
- Added logging filter to suppress SSL transport errors in LiteLLM.

### Changed
- Converted LiteLLM provider from sync `completion()` to async `acompletion()`, making `a_generate()` the primary implementation.
- Updated the RhesisLLM class to support asynchronous operations by replacing synchronous HTTP requests with aiohttp.
- Refactored synthesizer batch generation with retry mechanism.
- Made SDK model generation async-first.
- Updated garak to v0.14 with dynamic probe generation and code quality fixes.
- Centralized garak detectors in yaml registry.
- Converted RhesisLLM to async-first model with aiohttp integration.
- Converted VertexAILLM.generate to async a_generate.
- Updated various services to use async methods for testing model connections and generating test configurations.
- Renamed the docs/content/penelope directory to docs/content/conversation-simulation and updated the nav label to "Conversation Simulation".

### Fixed
- Fixed Bad Request Polyphemus Provider.
- Fixed issue where `_build_prompt` was duplicating description.
- Fixed env var clobbering that broke test migrations.
- Fixed Alembic migration parameterized SQL.
- Fixed no-op migration by sourcing garak v0.14 detector metrics directly from the SDK registry.
- Fixed issue where Goal line was not omitted in `_build_prompt` when no dedicated goal exists.
- Fixed hanging bug by updating litellm to 1.82.1.
- Fixed mutable default argument in synthesizer init.
- Fixed DeepEval test by using valid `tool_calls` data.
- Fixed issue where `add_message()` was storing the caller's dict by reference in `MessageHistoryManager`.
- Fixed null type in ProjectsQueryParams.$filter type.
- Fixed 21 Dependabot security vulnerabilities.
- Fixed disambiguation of duplicate project names and metric scope filter in frontend.

### Removed
- Removed unused auth0-lock dependency.


## [0.6.8] - 2026-03-05

### Added
- Added multi-file attachment support for tests, traces, and playground. This includes the ability to upload, download, and delete files associated with tests and test results.
- Added file format filters (to_anthropic, to_openai, to_gemini) for transforming input files into provider-specific content formats.
- Added file upload support to the `/chat` endpoint, allowing users to include files in chatbot conversations.
- Added file attachment support to WebSocket communication, enabling file transfers in chat applications.
- Added file upload button and drag-and-drop support to Playground chat.
- Added file download functionality to FileAttachmentList and MessageBubble components.
- Added file attachment support to multi-turn tests in Penelope.
- Added File entity to the SDK with upload, download, and delete capabilities.
- Added Azure AI Studio and Azure OpenAI providers as new LLM providers.
- Added `connect()` blocking API for connector-only scripts.
- Added JSON and Excel file upload support to the Playground.
- Added metadata and context as collapsible sections in the Test Run detail view.
- Added trace drawer and file sections to the Test Run detail view.
- Added required field validation to the metric creation form.

### Changed
- Renamed `run_connector` to `connect` in the SDK.
- Replaced test type magic strings with constants.
- Moved the file attachment button inside the text input in the Playground chat.
- Enhanced the constructors of OpenAILLM and OpenRouterLLM to accept additional keyword arguments.
- Updated Node.js version to 24 in CI configurations and Dockerfiles.
- Standardized file data field name from `content_base64` to `data`.
- Increased WebSocket max message size from 64KB to 10MB.

### Fixed
- Fixed an issue where `test_set_type_id` was not included when creating test sets from the manual writer.
- Fixed test set association and navigation issues in the manual test writer.
- Fixed focus loss in metric evaluation steps TextFields.
- Fixed lazy-load failures in mixin relationship properties in the backend.
- Fixed an issue where the test_type_id was overwritten on test updates.
- Fixed an issue where the polyphemus_access was null in user settings.
- Fixed an issue where the websocket tests were hanging due to incorrect MAX_MESSAGE_SIZE.
- Fixed an issue where MetricDataFactory was generating invalid metric test data.
- Fixed an issue where MarkdownContent was crashing when rendering JSON objects.
- Resolved TypeScript errors in model providers and test creation.
- Resolved focus loss in metric evaluation steps TextFields.
- Rebased file migration on litellm provider migration.
- Handled optional prompt_id in test components.
- Prevented test_type_id overwrite on update.
- Addressed PR review feedback.
- Added default for user_id in TestRunCreate schema.

### Removed
- Removed the `[DEBUG]` prefix from API error logs.


## [0.6.7] - 2026-03-02

### Added
- Added explicit `min_turns` parameter for early stop control in test configurations.
- Added test association methods (`add_tests()`, `remove_tests()`) to `TestSet` for bulk linking tests to test sets.
- Added `min_turns` and `max_turns` to import/export functionality (CSV, JSON, JSONL) and synthesizer.

### Changed
- Replaced instruction-based regex parsing for minimum turns with an explicit `min_turns` parameter on `execute_test()`.
- Replaced the max turns input on the frontend with a turn configuration range slider, allowing control of both `min_turns` and `max_turns`.
- Standardized naming: `max_iterations` is now `max_turns` throughout the SDK and backend.
- Improved turn budget awareness and deepening strategies for the Penelope agent.
- Enhanced metric update functionality to prevent overwriting with null values.
- Updated metrics page to paginate metrics fetch, ensuring all backend type tabs are displayed.
- Improved client-side pagination for the metrics grid.

### Fixed
- Prevented the goal judge from creating spurious turn count criteria.
- Addressed premature stopping and turn budget confusion in the Penelope agent.
- Stopped leaking turn budget into goal judge instructions.
- Corrected turn counting in conversational metrics to count user-assistant pairs.
- Prevented early stopping before reaching `max_turns`.
- Fixed focus loss and stale save button in the metric editor.
- Handled `None` turn parameters in test configuration.
- Fixed max-turns stop reason detection.
- Ensured conversational metrics receive `conversation_history` during evaluation.
- Fixed metric ID not being set after creation.
- Fixed default metric_scope for ConversationalJudge and GoalAchievementJudge.
- Fixed pagination robustness guards in the frontend.


## [0.6.6] - 2026-02-26

### Added
- Added debug logging to the synthesizer pipeline and LLM providers for diagnosing test generation failures.
- Added retry with exponential backoff to all LLM providers for handling transient errors.
- Added core Polyphemus integration, including service delegation tokens, access control, and a request/grant workflow.
- Added frontend support for Polyphemus model access, including an access request modal and model card UI states.
- Added conversation-based tracing across the SDK, backend, and frontend to link multi-turn conversation interactions.
- Added turn navigation to the sequence view in traces UI.
- Added a refresh button to trace filters.
- Added a full view button to the graph timeline.
- Added per-turn conversation I/O to trace spans for reconstructing multi-turn conversations.
- Added Redis-backed conversation linking cache with in-memory fallback for multi-worker environments.

### Changed
- Improved documentation for AI model configuration, clarifying dependencies between `RHESIS_API_KEY` and default models.
- Updated default generation and evaluation models to `rhesis/rhesis-default`.
- Restructured self-hosting AI configuration documentation.
- Updated dependencies to address security vulnerabilities, including `langchain-core`, `cryptography`, `pillow`, `fastmcp`, `redis`, `langgraph-checkpoint`, `marshmallow`, `virtualenv`, `mammoth`.
- Replaced `python-jose` with `PyJWT` for JWT handling.
- Improved traces UI with clickable responses and filter cleanup.
- Improved conversation detection and time formatting in traces.
- Improved traces UI with resizable width to trace detail drawer.
- Improved traces UI with turn labels on edges and slider marks in graph view.
- Improved traces UI with progressive agent invocation count on timeline.
- Improved traces UI with turn labels on edges in individual turn views.
- Updated edge handle routing in trace graphs for better visualization.
- Updated the traces UI to show the full trace ID in span details and truncate it in the list.

### Fixed
- Fixed Polyphemus configuration and connection test logic.
- Fixed issues with accessing response attributes in logging during tests.
- Fixed handling of LLM error responses in `TestSet.set_properties`.
- Fixed batch loop shortfall and added a zero-progress guard to prevent infinite loops.
- Fixed schema class name leaking into test set name.
- Fixed `ConversationalJudge` missing `id` attribute.
- Fixed security vulnerabilities reported by Dependabot.
- Fixed infinite loop in notification-dependent `useEffect` hooks.
- Fixed trace deduplication in list endpoint.
- Fixed conversation ID resolution in trace detail endpoint.
- Fixed bidirectional edges sharing connection points in trace graphs.
- Fixed missing `test_set_type` requirement on test set creation.
- Fixed potential data leakage by redacting request/response bodies from Polyphemus provider logs.
- Fixed a bug where missing `owner_id`/`user_id` would become the string `'None'` in a migration.
- Fixed the use of `FROM_EMAIL` for access review emails, replacing it with `POLYPHEMUS_ACCESS_REVIEW_EMAIL`.

### Removed
- Removed the duration filter (All/Normal/Slow) from TraceFilters in the UI.
- Removed `python-jose` from worker and polyphemus dependencies.


## [0.6.5] - 2026-02-18

### Added
- Added AI-powered auto-configuration for endpoints, analyzing reference material to generate request/response mappings. Includes LLM-driven analysis, endpoint probing, and prompt engineering.
- Added `Endpoint.auto_configure()` class method for code-first auto-configuration.
- Added Rhesis as the default embedding model provider.
- Added `Test Explorer` feature with adaptive testing support.
- Added drag-and-drop functionality to move tests between topics in the Test Explorer.
- Added `AddTestDialog` component for creating/editing tests in the Test Explorer.
- Added edit and delete actions to tests grid in the Test Explorer.
- Added `TopicDialog` component for creating/renaming topics in the Test Explorer.
- Added `DeleteTopicDialog` with impact summary in the Test Explorer.
- Added topic CRUD actions to tree view in the Test Explorer.
- Added clickable breadcrumb navigation for topics in the Test Explorer.
- Added `AdaptiveTestSetDrawer` for creating and editing test sets.
- Added `TestSet.pull()` with tests and `fetch_tests()` method.
- Added validation method to `TestTree` for topic marker checks.
- Added adaptive testing endpoints and service.
- Added adaptive testing pages and navigation.
- Added create topic endpoint and UI button.
- Added create test endpoint and UI.
- Added update test endpoint and edit dialog.
- Added drag-and-drop tests to topics.
- Added delete test endpoint and confirmation dialog.
- Added update topic endpoint with rename support.
- Added create adaptive test set endpoint and UI.
- Added generate outputs backend.
- Added Generate outputs UI and improve Add/Edit test form.
- Added topic selection and generate outputs button next to table.
- Added endpoint selection for output generation in AdaptiveTestingDetail component.
- Added metric selection functionality in AdaptiveTestingDetail component.

### Changed
- Unified `get_language_model()` and `get_embedding_model()` into a single `get_model()` method with auto-detection.
- Standardized terminology to 'language model' and 'embedding model'.
- Updated OpenAI generator to use new model initialization.
- Updated llm_endpoint prompts to include specific insurance offerings and guidelines for user interactions.
- Updated rhesis_scorer prompts to clarify the context of the insurance chatbot and its compliance rules.
- Updated TestTreeBrowser to utilize new functions for score removal and evaluation status setting, improving code clarity and maintainability.
- Updated TestTreeBrowser to dynamically generate new topic names based on the current topic, improving usability.
- Updated the TestTree class to store all relevant node fields (tree_id, output, label, labeler, model_score) in metadata for complete round-trip support.
- Updated the logic for building node kwargs in the TestTree class to prioritize using the test.id (database ID) when available, falling back to the tree_id from metadata if not.
- Updated the navigation items to include the 'Adaptive Testing' page only in the development environment, enhancing the development experience without affecting production.
- Renamed `create` method to `add_topic` for clarity.
- Renamed `Topic` to `TopicNode` for clarity.
- Migrated from `requests` to `httpx` for async support in `RestEndpointInvoker`.
- Enhanced output generation with concurrent endpoint invocations.

### Fixed
- Fixed redirect after endpoint creation.
- Fixed ambiguous label queries in auto-configure tests.
- Fixed test timeouts in auto-configure tests.
- Fixed UnmappedClassError in tests.
- Fixed auth token substitution to support custom headers.
- Fixed topic formatting and assertions in test cases.
- Fixed get_all_parents returning strings instead of TopicNodes.
- Fixed test tree order in TestSet round-trip.
- Fixed get_all_parents returning strings instead of TopicNodes.
- Fixed frontend test filtering logic to only check for exact matches with the selected topic.
- Fixed frontend to allow creating topic when no topics in adaptive testing.
- Fixed frontend to ensure InputLabel shrinks for topic selection in AdaptiveTestingDetail component.
- Fixed backend to use per-task db sessions in generate_outputs_for_tests.
- Fixed tests to reset worker cache in telemetry enrichment service tests.

### Removed
- Removed get_language_model(), get_embedding_model(), and get_embedder(). Use get_model() instead.
- Removed llm_endpoint function.
- Removed description field from TestTree and TestTreeBrowser.
- Removed obsolete sequence classification tests CSV file.
- Removed global embedder state in adaptive testing.
- Removed unused str property from TestTree.
- Removed profanity filter from LLMGenerator.
- Removed adaptive testing router, schemas, and service.
- Removed profanity dependency from adaptive testing.
- Removed test explorer feature.

### Security
- Added API key detection and redaction for auto-configure to prevent real API keys from being sent to the LLM.
- Added SSRF protection to block cloud metadata services while allowing localhost.

### Breaking Changes
- Removed `get_language_model()`, `get_embedding_model()`, and `get_embedder()`. Use `get_model()` instead which auto-detects model type from name or accepts explicit `model_type` parameter.


## [0.6.4] - 2026-02-12

### Added
- Added split-view playground and test creation from conversations, including endpoints and a drawer with LLM-extracted pre-filled fields for both single-turn and multi-turn tests.
- Added file import for test sets, supporting CSV, JSON, JSONL, and Excel formats with column mapping, auto-mapping with confidence, and user-friendly error handling.
- Added flat convenience fields (goal, instructions, restrictions, scenario) for multi-turn test configuration on the `Test` entity in the SDK.
- Added server-side filtering to the test sets grid, enabling column filters for name, type, creator, and tags.
- Added `rescore()`, `last_run()`, and metric management methods (`get_metrics()`, `add_metric()`, `remove_metric()`) to `TestSet` for enhanced test execution control.
- Added `get_available_embedding_models` and `get_available_llm_models` factory functions, and `get_available_models` and `push` methods on `BaseEmbedder` and `LiteLLMEmbedder` for embedding model support.
- Added user-configurable embedding model support, including a new `DEFAULT_EMBEDDING_MODEL` constant and embedding settings in user preferences.
- Added support for testing embedding model connections in addition to LLM models.
- Added `ExecutionMode` enum (`PARALLEL`, `SEQUENTIAL`) and validation for `execute()` and `rescore()`.

### Changed
- Refactored the multi-turn synthesizer to use a flat schema for batch generation, improving efficiency and consistency.
- Replaced Auth0 with a native authentication system, including email/password, Google OAuth, and GitHub OAuth providers.
- Updated default generation model to `rhesis/default` for out-of-the-box functionality without external API keys.
- Improved error messages for model configuration and worker availability, providing clear, actionable guidance to users.
- Reduced access token lifetime to 15 minutes and introduced opaque refresh tokens with rotation and reuse detection for enhanced security.
- Updated `bulk_create_tests` to return a list of ID strings instead of `models.Test` objects for memory optimization.

### Fixed
- Enforced newline-separated steps in synthesizer instructions for better LLM parsing.
- Restored the copy button on assistant messages in the frontend.
- Fixed an issue where multi-turn imports were incorrectly created as single-turn during file import.
- Fixed session hijacking vulnerabilities in the file import flow by adding user/organization ownership verification.
- Resolved numerous pytest warnings in the SDK test suite.
- Fixed retry kwargs dropping `reference_test_run_id` and `trace_id` in the execution pipeline.
- Fixed an issue where the UI flickered during auto-advance in the file import mapping UI.
- Fixed handling of optional dimension and demographic in `create_prompt` to avoid `NotNullViolation`.
- Fixed an open redirect vulnerability in the native authentication system by implementing exact domain validation.
- Fixed an issue where the verification banner didn't hide immediately after email verification.
- Fixed a bug where the quick start admin user was not marked as email verified.
- Fixed an issue where the Rhesis default model validation was not being performed correctly.
- Fixed a bug where validation warnings were not cleared when models were no longer defaults.
- Resolved Python security vulnerabilities in dependencies.

### Removed
- Removed user-configurable embedding dimensions, as these are now determined automatically by the model provider.
- Removed duplicated `push()` function from `LiteLLMEmbedder`.
- Removed Azure OpenAI and Auth0 secrets from workflows and deployment configurations.


## [0.6.3] - 2026-02-05

### Added
- Added a new interactive endpoint playground accessible under the "Testing" section. This allows real-time WebSocket communication for conversational endpoint testing, including chat message handling, TraceDrawer integration, and session management.
- Added JSON and JSONL import/export functionality for TestSets, enabling users to easily load and save test data.
- Added a "Playground" button to the endpoint detail page, pre-selecting the endpoint in the playground.
- Added markdown rendering to playground chat bubbles for improved readability.
- Added a copy button to playground message bubbles for easy content sharing.
- Added a graph view for trace visualization, providing an alternative to the tree view.
- Added framework-agnostic agent tracing support with new span types and attributes for multi-agent systems.
- Added CompiledGraph patching for LangGraph auto-instrumentation, simplifying callback injection.
- Added lm-format-enforcer as a new provider.

### Changed
- Increased the default SDK function timeout from 30s to 120s, configurable via the `SDK_FUNCTION_TIMEOUT` environment variable.
- Increased SDK connector ping interval/timeout defaults to 60s/30s, configurable via `RHESIS_PING_INTERVAL` and `RHESIS_PING_TIMEOUT` environment variables.
- Standardized `session_id` as the canonical name for conversation tracking, normalizing various field names.
- Enhanced the WebSocket retry mechanism with increased reconnect attempts, a maximum reconnect delay, and a manual reconnect method.
- Improved token extraction from LLM responses with support for various token sources and metadata formats.
- Refactored the LangChain integration for better modularity and maintainability.
- Adjusted the trace detail view split to 70:30, giving more space to the trace visualization.
- Replaced the agent icon with a brain icon for better visual consistency.
- Updated Gemini model example to `gemini-2.0-flash`.

### Fixed
- Fixed an issue where synchronous endpoint functions would block the event loop, causing WebSocket ping timeouts. Now, they run in a thread pool.
- Fixed Redis URL configuration to prioritize `BROKER_URL` for consistency.
- Fixed connector test isolation issues by addressing mock behavior and executor input handling.
- Fixed trace_id propagation from the SDK to the frontend for trace linking in synchronous functions.
- Fixed an issue where only the sessionId was reset when switching endpoints in the playground; now all state is cleared.
- Fixed AttributeError in HuggingFaceLLM `__del__` method.
- Fixed overwriting of passed kwargs.

### Security
- Upgraded `protobuf` to >=3.25.5 to address CVE-2026-0994 (JSON recursion depth bypass).
- Upgraded `python-multipart` to >=0.0.22 to address CVE-2026-24486 (arbitrary file write).


## [0.6.2] - 2026-01-29

### Added

- Added Model entity with provider auto-resolution. Accepts provider name string (e.g., "openai") instead of UUID, auto-resolves via type_lookups API, includes user settings management for default generation/evaluation models, and get_model_instance() for converting to BaseLLM. (#1132)
- Added Project entity with comprehensive integration tests for CRUD operations. (#1127)
- Added batch processing with generate_batch method for LiteLLM-based providers supporting system prompts, schemas, and multiple completions per prompt. (#1149)
- Added embedders framework with BaseEmbedder class, LiteLLMEmbedder, OpenAIEmbedder, GeminiEmbedder, and VertexAIEmbedder for generating single and batch embeddings. (#1149)
- Added Vertex AI support with VertexAIEmbedder and VertexAILLM classes including credential handling and configuration loading. (#1149)
- Added GarakDetectorMetric class for evaluating LLM responses using Garak detectors with threshold-based probability scoring. (#1190)
- Added ObservableMCPAgent with OpenTelemetry tracing for automatic LLM and tool invocation tracing using @observe decorators and semantic spans. (#1102)
- Added PATCH method to Methods enum in APIClient for partial resource updates. (#1165)
- Added context and expected response fields display support for test run detail view. (#1201)

### Changed

- Refactored metrics context validation to SDK. Metrics requiring context now return visible failure results with unified error messages ("<metric> metric requires context to evaluate. No context was provided.") instead of being silently skipped. Removed unused 'error' field from SDK metric results. (#1200)
- Enhanced Endpoint class with request_mapping, request_headers, response_mapping, auth_token, method, endpoint_path, and query_params fields for full programmatic configuration. Added write-only fields support to handle sensitive fields like auth_token in pull-modify-push workflows. (#1189)
- Separated API client from observability client (APIClient vs RhesisClient). RhesisClient is now optional in production, with from_environment() factory that gracefully falls back to DisabledClient when credentials are missing. (#1155)
- Added copy button to documentation code blocks and improved navigation spacing. (#1177)
- Upgraded security-related dependencies to address vulnerabilities. (#1174)
- Standardized context and ground truth requirements across DeepEval and Ragas metrics with consistent requires_context and requires_ground_truth attributes. (#1201)

### Fixed

- Fixed connector disabled variable handling. Changed RHESIS_CONNECTOR_DISABLE to RHESIS_CONNECTOR_DISABLED and updated workflow environment variables. (#1167)
- Fixed SDK entity bugs: TestRun.status now properly extracts status from nested dict, TestSet.test_set_type validator extracts type_value correctly. Added Endpoints collection class for name-based retrieval. (#1129)
- Fixed backend test cleanup transaction errors by combining all database operations into a single transaction. Added proper asyncio.CancelledError handling and RuntimeError prevention during SDK connector initialization. (#1142)
- Updated langchain-core to 1.2.5 and urllib3 to 2.6.3 to address security vulnerabilities. (#1160)
- Updated aiohttp to fix compatibility issues. (#1164)
- Fixed database connection leak with generator-based dependency cleanup in @endpoint decorator, similar to FastAPI's Depends with yield pattern. (#1102)
- Fixed resource leak on bind param initialization failure by ensuring cleanup handlers are populated in-place for partial failure cleanup. (#1102)



## [0.6.1] - 2026-01-15

### Added
- Implemented continuous slow retry mode for connector resilience. This new mode allows the SDK to automatically retry failed connector operations with increasing delays, improving stability and reliability in unstable network environments. (#1123)


## [0.6.0] - 2026-01-15

### Added
- Added `bind` parameter to the endpoint decorator for dependency injection, enabling more flexible endpoint configurations.
- Added name-based entity lookup in the SDK `pull` method, allowing for easier retrieval of entities.
- Added `project_id` field and `ConnectionType` enum to the `Endpoint` class.
- Added OpenTelemetry integration and a basic telemetry system for enhanced observability.
- Added Github MCP Provider for connecting to Github resources.
- Added Chatbot Intent Recognition functionality.

### Changed
- Enhanced SDK tracing with asynchronous support, smart serialization, and improved I/O display for better debugging and performance analysis.
- MCP connection logic has been improved for increased reliability and stability.
- MCP now supports multiple transport protocols.
- Implemented a bucket model for improved data handling.


## [0.5.2] - 2025-12-18

### Added
- Added support for categories and threshold operators for metrics.
- Introduced a new Polyphemus provider with schema support.

### Changed
- Improved generation prompts with research-backed Chain-of-Thought (CoT) and a balanced testing framework.
- Enhanced SDK test configuration and result reporting.
- Improved MCP (Managed Configuration Platform) error handling and usability.

### Fixed
- Fixed metric creation to support both SDK and frontend approaches with proper field handling.
- Hotfix for MCP compatibility issues with `npx` and `bunx`.


## [0.5.1] - 2025-12-01

### Added
- Added support for OpenRouter as a provider.
- Added Rhesis SDK examples.

### Changed
- Enhanced Penelope notebooks with configuration sections.

### Fixed
- Fixed API key issues in Penelope notebooks.


## [0.5.0] - 2025-11-27

### Added
- Added bidirectional SDK connector with intelligent auto-mapping.
- Added comprehensive multi-turn test support.
- Added support for Google Cloud integration (Polyphemus).
- Added functionality to list available models for providers.

### Changed
- Improved synthesizers for enhanced performance and functionality.
- Refactored base entity for improved code structure and maintainability.
- Updated MCP Tool Database functionality.

### Fixed
- Fixed multi-turn test generation response format.
- Fixed MCP Tool arguments.
- Ensured correct `test_type` for single and multi-turn tests.
- Resolved test failures and improved schema design.
- Fixed Ollama provider compatibility.

### Removed
- Removed `synthesizers_v2`.


## [0.4.2] - 2025-11-17

### Added
- Added support for custom HTTP headers in API requests. Users can now configure specific headers for authentication or other purposes.

### Changed
- Improved error handling for network requests. More descriptive error messages are now provided to the user.
- Updated the internal retry mechanism for failed API calls to be more robust.

### Fixed
- Fixed an issue where the SDK would incorrectly parse dates in certain locales.
- Resolved a bug that caused occasional crashes when handling large data responses.


## [0.4.1] - 2025-11-13

### Added
- Added support for Penelope Langchain integration.
- Added LangGraph metrics example.
- Added multi-turn test synthesizer functionality.
- Added scenarios feature for test case generation.
- Added cost heuristic for Polyphemus benchmarking.
- Added schema support for Hugging Face models.
- Added SDK support for metric scope and test set type.
- Added example workflow demonstrating MCPAgent usage.
- Added schemas for search and extraction results within MCPAgent.
- Added `stop_on_error` parameter to MCPAgent.
- Added Endpoint entity with invoke method for easier API interaction.
- Implemented structured output for tool calling via Pydantic schemas.
- Implemented native Rhesis conversational metrics with Goal Achievement Judge.
- Added core conversational metrics infrastructure, including Turn Relevancy and Goal Achievement.
- Added goal-achievement-specific template with excellent defaults for metrics.
- Added ConversationalJudge architecture demo.
- Added comprehensive GoalAchievementJudge test cases.
- Added optional `chatbot_role` support in conversational metrics.

### Changed
- Refactored MCPAgent to accept `Union[str, BaseLLM]` for the `model` parameter.
- Renamed `llm` parameter to `model` in MCPAgent for consistency.
- Refactored MCPAgent architecture for improved modularity and reusability.
- Consolidated agent ReAct loop into BaseMCPAgent.
- ConversationalJudge is now numeric by default.
- Upgraded DeepEval dependency to version 3.7.0.
- Output size now defaults to 2048 tokens.

### Fixed
- Resolved linting issues in various SDK components.
- Improved VertexAI provider reliability and error handling.
- Resolved Vertex AI empty OBJECT properties error in MCPAgent.
- Improved JSON parsing error handling in MCPAgent.
- Fixed Hugging Face model loading behavior.
- Fixed comprehensive code review fixes for multi-turn metrics.

### Removed
- Removed obsolete design documents.
- Removed non-conversational DeepEval metrics.
- Removed provider-specific filtering from MCPAgent executor.
- Removed application-specific schemas from MCPAgent.
- Removed redundant verbose output in MCPAgent.
- Removed old files after MCPAgent restructure.
- Removed sql alchemy dependency.


## [0.4.0] - 2025-10-30

### Added
- Added Vertex AI provider with hybrid authentication support.
- Added Cohere model support.
- Added support for both plain and OpenAI-wrapped JSON schemas in LLM providers.
- Added iteration context support to test generation.
- Added source_id tracking to tests generated from documents.
- Integrated Ragas metrics for evaluating RAG systems, including faithfulness and aspect critic metrics.
- Integrated enhanced DeepEval metrics, including a bias metric.
- Added DeepTeam model support.

### Changed
- Refactored metrics to use a new configuration-based initialization, improving validation and flexibility.
- Updated DeepEval integration to be compatible with v3.6.7 API.
- Improved LLM error logging with full traceback.
- Optimized Vertex AI model and region defaults.
- Enhanced AI-based test generation with improved UI and backend support.
- Simplified schema wrapping logic in RhesisLLM.
- Refactored the metrics module for improved organization and maintainability.
- Updated supported file types for source extraction.

### Fixed
- Fixed Hugging Face imports.
- Fixed `_create_ollama_llm` initialization error.
- Corrected schema type hints in `RhesisLLM` and `VertexAILLM`.
- Corrected type hint in `validate_llm_response`.
- Corrected supported params for `RhesisPromptMetricCategorical`.
- Handled OpenAI-wrapped schemas in LLM providers.
- Fixed handling of missing DeepEval metrics in older versions.
- Fixed line length linting errors.
- Fixed various bugs in metrics and tests.
- Fixed issues with Ragas metrics initialization and usage.
- Fixed issues with DeepEval model initialization.
- Fixed UTF-8 encoding for markitdown text extraction.

### Removed
- Removed optional DeepEval metric imports.
- Removed unused `LLMService` class.
- Removed unnecessary markdown stripping in `LiteLLM`.
- Removed unused `NumericDetailedJudge` from factory.


## [0.3.1] - 2025-10-16

### Added
- Added support for user-defined LLM provider generation and execution.
- Enhanced `DocumentExtractor` with `BytesIO` support for processing documents from memory.
- Added `model` parameter support to the synthesizer factory, allowing specification of the LLM model to use.

### Changed
- Updated `ParaphrasingSynthesizer` to utilize the `model` parameter for LLM selection.
- Modernized SDK documentation with Rhesis AI branding.

### Fixed
- Corrected the class name for DeepEval context relevancy metrics.
- Resolved an issue related to worker-based generation.
- Fixed an issue where the `main` branch might be missing in the Makefile git diff.
- Fixed an error when pulling metrics.
- Removed `schema` from kwargs to resolve an issue.

### Removed
- (None)


## [0.3.0] - 2025-10-02

### Added
- Added `push` functionality to `PromptMetricCategorical` and `PromptMetricNumeric` for submitting metric data.
- Added `pull` functionality to `PromptMetricCategorical` and `PromptMetricNumeric` for retrieving metric data by name or ID.
- Added `from_config` method to `PromptMetric` for easier instantiation from configuration.
- Added `sdk_config_to_backend_config` and `backend_config_to_sdk_config` functions for configuration conversion.
- Added parameter and URL parameter processing in the SDK client.
- Added metrics endpoint to the SDK client.

### Changed
- Refactored metric backend to use Rhesis instead of native.
- Refactored common metric functionality into base classes.
- Improved metric configuration to accept enums.
- Improved configuration handling for metrics.
- Updated `BaseMetric` to accept enums for categorical metrics.

### Fixed
- Resolved linting errors in test_metric.py.
- Fixed default arguments for `prompt_metric_categorical`.
- Fixed metric backend configuration.
- Fixed enum and string validation in metrics.
- Fixed handling of categories in `PromptMetric`.
- Fixed raising errors for incorrect metric types.
- Fixed prompt metric imports.
- Fixed test data leakage in `test_metric.py`.
- Fixed handling of `None` config in prompt synthesizer.


## [0.2.4] - 2025-09-18

### Added
- Added `DocumentSynthesizer` for document text extraction and chunking, enabling the creation of context from documents.
- Added `ContextGenerator` service with semantic chunking for improved context selection.
- Added support for Ollama LLM provider.
- Added document source tracking to `DocumentSynthesizer`.
- Added `strategy` parameter to `DocumentSynthesizer` for sequential vs random context selection.
- Added comprehensive user feedback for test generation plan.

### Changed
- Refactored benchmarking framework to integrate SDK modules and improve model handling.
- Refactored `PromptSynthesizer` to use context instead of documents.
- Refactored `RhesisPromptMetric` for improved performance and maintainability.
- Updated `DocumentSynthesizer` to use `Document` dataclass instead of dictionaries.
- Updated LLM providers to inherit from LiteLLM for GeminiLLM and OpenAILLM.
- Improved model factory for easier model selection and configuration.
- Metrics now accept a model directly, allowing for more flexible model integration.
- Replaced `ContextSynthesizer` with `ContextGenerator` service.
- Enforced hard size limits with semantic-first splitting in `ContextGenerator`.

### Fixed
- Fixed batch size None comparison error.
- Fixed testset generation issues.
- Fixed minor issues in LLM provider implementations.
- Fixed template path for metrics.
- Fixed Python package version conflicts.

### Removed
- Removed `pyarrow` dependency to reduce environment and Docker image sizes.
- Removed the template caching mechanism.
- Removed binary and categorical functionality from prompt metrics.
- Removed the absolute_max_context_tokens limit.
- Removed document support from `PromptSynthesizer`.
- Removed the need for API keys in some configurations.


## [0.2.3] - 2025-09-04

### Added
- Support for JSON schema definitions in LLM service requests, allowing for structured responses.
- Integration with Gemini and OpenAI LLMs via the LLM service.
- API key handling for LLM providers.
- Basic tests for base LLM and model factory.
- Tests for SDK service utilities.

### Changed
- **Breaking Change:** Renamed `rhesis_provider` to `native`.
- **Breaking Change:** Renamed `openai_provider`.
- **Breaking Change:** Renamed `gemini`.
- **Breaking Change:** Renamed `factory`.
- **Breaking Change:** Renamed `rhesisllmservice`.
- Refactored LLM service architecture, including moving `basellm`, `utils`, and `modelfactory` to new locations.
- Renamed the `response_format` argument to `schema` for clarity and consistency.
- Improved code structure and cleanliness in Gemini and OpenAI providers.
- Updated linting process to use `uvx` instead of `uv run`.
- Refactored prompt synthesizers to use helper functions for code reuse and improved maintainability.
- Renamed 'document context' to the more generic 'context' in relevant components.

### Fixed
- Fixed a bug in the Rhesis (now Native) LLM service.
- Fixed issues with the Rhesis provider.

### Removed
- Removed `pip` from SDK dependencies.


## [0.2.2] - 2025-08-22

### Added
- Support for extracting content from `.docx`, `.pptx`, and `.xlsx` file formats.

### Changed
- Migrated document extraction from `docling` to `markitdown` for improved performance and format support.
- Improved code style and consistency across the SDK.
- Enhanced linting and formatting processes using `ruff` via Makefile improvements and a pre-commit hook at the root level.

### Removed
- Support for extracting content from `.url` and `.youtube` file extensions.


## [0.2.1] - 2025-08-08

### Added
- Added `get_field_names_from_schema` method to the `BaseEntity` class. This method retrieves field names from the OpenAPI schema, enabling dynamic access to entity properties.

### Changed
- Updated the default base URL for the API endpoint.

### Fixed
- Fixed an issue with the default base URL for API endpoint.

### Documentation
- Improved the readability and logical flow of the contributing guide.
- Enhanced the styling of the contributing guide for better user experience.


## [0.2.0] - 2025-07-25

### Added
- Added `documents` parameter to `PromptSynthesizer` for enhanced document handling.
- Added `DocumentExtractor` class with support for `.txt` files.
- Added synthesizer factory to SDK for easier synthesizer creation.
- Added custom behavior informed by prompt to `PromptSynthesizer`.

### Changed
- Adjusted `PromptSynthesizer` to allow custom behaviors.

### Fixed
- Corrected typos and formatting errors in documentation and code.

### Removed
- Removed tag creation from the release script.

### Documentation
- Updated `CONTRIBUTING.md` to include MacOS setup instructions.
- Updated general documentation.

- Ongoing development within the main repo structure
- Integration with other main repo components

## [0.1.9] - 2025-05-15

### Added
- Added rhesis namespace - now accessible via `rhesis.sdk`

### Changed
- Migrated to uv for package management, a more modern approach

## [0.1.8] - 2025-04-30 (Included in repository-wide v0.1.0 release)

### Added
- Support for custom test templates
- New paraphrasing capabilities
- Additional LLM service integrations
- Better documentation structure within Sphinx

### Changed
- Versioning in documentation is linked to source files in the code base

### Fixed
- Issue with token handling in the API client
- Performance improvements in test generation
- Documentation build issues that were generating warnings in Sphinx

## [0.1.7] - 2025-04-17

### Added
- Added test set upload functionality

### Changed
- Improved synthesizers and LLM generation functionality

### Fixed
- Fixed method naming issues

## [0.1.6] - 2025-04-14

### Added
- Added run method to LLM Service for improved convenience
- Added new Prompt and Test entity classes
- Added automatic test set description generation
- Added set_attributes() method to TestSet class
- Added support for custom system prompts in synthesizers

### Changed
- Changed TestSet to work with tests instead of prompts
- Changed synthesizers to use new test-focused entity model
- Changed prompt templates to match new test entity format

### Removed
- Removed direct prompt handling from TestSet class
- Removed old prompt-based test set generation

### Fixed
- Fixed synthesizer response parsing to handle new test structure
- Fixed test set property extraction to work with nested test objects

## [0.1.5] - 2025-02-21

### Added
- Added ParaphrasingSynthesizer for generating paraphrases of test cases

## [0.1.4] - 2025-02-20

### Added
- Added CLI scaffolding for rhesis

## [0.1.3] - 2025-02-19

### Added
- Added new test set capabilities
- Added PromptSynthesizer for generating test sets from prompts
- Added example usage for PromptSynthesizer

## [0.1.2] - 2025-02-18

### Added
- Added new topic entity
- Added base entity for CRUD testing
- Added topic tests

## [0.1.1] - 2025-02-17

### Added
- Added support for Parquet files
- Added more entities and functionality

## [0.1.0] - 2025-01-26

### Added
- Initial release of the SDK
- Core functionality for test set access
- Basic documentation and examples
- Basic unit tests and integration tests


[Unreleased]: https://github.com/rhesis-ai/rhesis/compare/sdk-v0.1.9...HEAD
[0.1.9]: https://github.com/rhesis-ai/rhesis/releases/tag/sdk-v0.1.9
[0.1.8]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.8
[0.1.7]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.7
[0.1.6]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.6
[0.1.5]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.5
[0.1.4]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.4
[0.1.3]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.3
[0.1.2]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.2
[0.1.1]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.1
[0.1.0]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.0
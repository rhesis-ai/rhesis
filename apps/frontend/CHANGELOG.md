# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.6] - 2026-02-26

### Added

- Added support for Polyphemus model access control, including an access request modal, API route, model card UI states, and a Polyphemus provider icon and logo.
- Added a conversation traces UI to surface multi-turn conversation traces. This includes a conversation icon in the trace list, type filter buttons, a Conversation View tab in the trace drawer, turn labels on root spans in the tree view, and turn navigation buttons in the graph view and sequence view.
- Added a refresh button to trace filters.
- Added a full view button to the graph timeline.
- Added per-turn conversation input/output attributes to trace spans, enabling the frontend to reconstruct multi-turn conversations from span data.
- Added a drag handle to the trace detail drawer, allowing users to resize the drawer width.

### Changed

- Improved the traces UI with clickable responses in Conversation View and cleaned up filters.
- Shortened the trace ID column in the list view and displayed the full trace ID in the span details panel.
- Stabilized `show`/`close` callbacks in `NotificationContext` to prevent infinite loops.
- Updated test set selection dialog to filter by `test_set_type_id` instead of `test_type_id`.
- Updated the trace list endpoint to deduplicate traces by `trace_id`, preventing duplicate entries for conversation traces.
- Replaced the separate `count_traces` call with a window function to improve performance.
- Improved conversation detection in `TestResultTab` and switched to `formatDistanceToNowStrict` for consistent time display in `TracesTable`.
- Moved turn navigation above time controls in the graph view.
- Turn labels are now displayed on edges in all modes of the graph view.
- The agent node count chips on the timeline now increment progressively.
- The conversation linking caches are now backed by Redis with an in-memory fallback, fixing multi-worker race conditions.

### Fixed

- Fixed critical, high, medium, and low severity security vulnerabilities in frontend transitive dependencies by adding overrides for various packages.
- Fixed an issue where the trace detail endpoint used the wrong span to resolve the conversation ID.
- Fixed an issue where first-turn traces for stateful endpoints were not linked to the conversation.
- Fixed an issue where the test set selection dialog was filtering by test type ID instead of test set type ID.
- Fixed an issue where test sets could be created without a test set type.
- Fixed an issue where tests could be assigned to test sets with mismatched types.

## [0.6.5] - 2026-02-18

### Changed

- Evaluate three-tier metrics during live multi-turn execution (#1366)

* feat: evaluate three-tier metrics during live multi-turn execution

Previously, only Penelope's Goal Achievement metric was evaluated during
live multi-turn test execution. Additional metrics defined in the
three-tier model (behavior > test set > execution) were ignored.

Backend: add exclude_class_names to evaluate_multi_turn_metrics() and
call it after Penelope's evaluation to pick up additional metrics.
Frontend: show metrics table for multi-turn tests with additional
metrics and use all metrics for pass/fail determination.

- fix(test): update multi-turn runner tests for additional metrics evaluation

Update test expectations to reflect that evaluate_multi_turn_metrics is
now called during live execution to pick up additional three-tier
metrics. Add test for merging additional metrics with Penelope results.

- Fix e2e projects content test selectors (#1365)

* fix(e2e): fix projects content test selectors

Add networkidle wait, use .MuiCard-root instead of [class*="ProjectCard"],
and broaden create button detection to include link role.

- fix(e2e): use resilient selectors in projects content test

Restore broader /create|new/i regex for create button matching and
replace generic main element fallback with projects-specific heading.

- Add AI-powered auto-configure for endpoint mappings (#1364)

* feat(backend): add auto-configure endpoint service

Add AI-powered auto-configuration that analyzes user-provided reference
material (curl commands, code snippets, API docs) and generates Rhesis
request/response mappings. Includes LLM-driven analysis, endpoint
probing with self-correction, and comprehensive prompt engineering for
conversation mode detection and platform variable mapping.

- feat(frontend): add auto-configure modal and UI

Add AutoConfigureModal with two-step stepper (input + review), integrate
auto-configure button in endpoint creation form, move auth token to
basic info tab, and fix project-context redirect after creation.

- fix(frontend): fix redirect after endpoint creation

Remove /endpoints suffix from project-context redirect so it navigates
to the project detail page instead of a non-existent route.

- feat(sdk): add auto_configure class method to Endpoint

Add Endpoint.auto_configure() for code-first auto-configuration using
the backend service, with probe control and result inspection.

- docs: update endpoint docs for auto-configure and platform variables

Add auto-configure documentation page. Update platform variable tables
to include all managed fields (conversation_id, context, metadata,
tool_calls, system_prompt). Fix conversation_id scope to cover all
conversational endpoints, not just stateful. Add response mappings for
tool_calls and metadata in provider examples.

- refactor(backend): restructure auto-configure prompts with endpoint taxonomy

Rewrite both auto_configure.jinja2 and auto_configure_correct.jinja2
around a clear hierarchical taxonomy: single-turn vs multi-turn
(stateless | stateful). This replaces the previous flat three-category
approach with a two-step classification that improves LLM accuracy.

- feat(backend): add API key detection and redaction for auto-configure

Prevent real API keys from being sent to the LLM during auto-configure.
Backend redacts secrets (OpenAI, AWS, Google, Bearer tokens) before
prompt rendering. Frontend shows a warning and blocks submission when
keys are detected. Environment variable placeholders are preserved.

- chore: update chatbot uv.lock

- style(frontend): use theme borderRadius in AutoConfigureModal

- fix(frontend): resolve ambiguous label queries in auto-configure tests

Use getByRole('textbox') instead of getByLabelText to avoid matching
the Tooltip aria-label on the disabled Auto-configure button. Also
prefix unused FAILED*RESULT fixture with * to fix eslint warning.

- ci: ignore empty uv cache in sdk test workflow

The uv cache clean step wipes the cache directory, causing the
post-job save to fail. Add ignore-nothing-to-cache to prevent this.

- fix(frontend): resolve test timeouts in auto-configure tests

Use userEvent.setup({ delay: null }) to remove inter-keystroke delays
that caused CI timeout exceeding the 5s limit.

- fix: resolve lint errors and test timeouts

- chore: formatting and lint fixes

- fix(backend): resolve UnmappedClassError in tests

- fix: address PR #1364 review comments

* Update schema: request_mapping and response_mapping now support nested JSON (Dict[str, Any])
* Add SSRF protection: block cloud metadata services (169.254.0.0/16) while allowing localhost
* Fix auth token substitution: support custom headers like x-api-key, not just Authorization
* Update LLM prompts: clarify nested JSON support and warn against mapping $.id to conversation_id
* Improve UX: remove auth_token requirement for auto-configure (support open APIs)
* Fix: pre-existing TypeScript error in BehaviorsClient.tsx

Addresses all 5 issues raised by @peqy in PR review.

- Add default Rhesis embedding model and standardize terminology (#1355)

* feat: consistently use 'language model' instead of 'llm model'

* feat: standardize terminology to 'language model' and 'embedding model'

- Rename get_model() → get_language_model() and get_embedder() → get_embedding_model()
- Rename ModelConfig → LanguageModelConfig and EmbedderConfig → EmbeddingModelConfig
- Keep deprecated aliases for backward compatibility

* feat: use consistent naming for language and embedding model in tests and backend

* feat(sdk): get_model to get_language_model for clarity

- Renamed get_model() to get_language_model() across SDK
- Renamed DEFAULT_MODEL_NAME to DEFAULT_LANGUAGE_MODEL_NAME in all providers
- Renamed PROVIDER_REGISTRY to LANGUAGE_MODEL_PROVIDER_REGISTRY

* feat(test): update tests for renaming in SDK

* refactor: rename model config vars for clarity

Rename DEFAULT_GENERATION_MODEL → DEFAULT_LANGUAGE_MODEL_PROVIDER and DEFAULT_MODEL_NAME → DEFAULT_LANGUAGE_MODEL_NAME across all services

- rename model_type to purpose

* rename model_type to purpose in \_get_user_model and related functions to avoid confusion between model_type terminology (which refers to whether model is either language/embedding model)

- refactor(frontend): change model_type from llm -> language

- refactor(sdk): change llm to language in model_type param

- feat: add default rhesis embedding model support

Add Rhesis as the default embedding model provider, following the same pattern as the language model:

Backend changes:

- Update constants to use consistent naming (DEFAULT_EMBEDDING_MODEL_PROVIDER)
- Create default Rhesis embedding model during organization initialization
- Store both language_model_id and embedding_model_id in user settings
- Update generate/embedding endpoint to use new constants

SDK changes:

- Implement complete RhesisEmbedder class with generate() and generate_batch()
- Add factory function for Rhesis embedding model
- Register "rhesis" provider in EMBEDDING_MODEL_REGISTRY
- Update DEFAULT_EMBEDDING_MODEL_PROVIDER from "openai" to "rhesis"

This enables users to use Rhesis-hosted embeddings by default while still allowing custom embedding model configuration.

- change from 'language_model' to 'model' in schemas, routers and model connection

- fix: import in tests and remove unused aliases

* use correct import (DEFAULT_LANGUAGE_MODEL_PROVIDER) in tests
* remove unused aliases (DEFAULT_MODELS, DEFAULT_PROVIDER)

- fix(test): use rhesis default embedding model

- fix: import

- fix(test): 'get_model'-> 'get_language_model'

- fix(alembic): resolve head conflict and add hash-like id to alembic filename

- fix: mock using get_language_model

- style: reformat imports

- docs: update documentation with new get_language_model and get_embedding_model

- feat(frontend): add rhesis default embedding model

- fix: add DEFAULT_EMBEDDING_MODEL_PROVIDER and DEFAULT_EMBEDDING_MODEL_NAME in infrastructure, docs and github workflow files

- feat: add new migration to add defaul Rhesis embedding model to all existing organizations

- fix(test): add missing description parameter

- chore: restore github workflows variable as in main branch

- chore: restore env example and docker compose file as to main

- chore: restore unrelated github workflows files as in main

- chore: restore tests as in main

- chore: restore sdk files as in main

- chore: restore docs files as in main

- chore: restore backend and chatbot files as in main

- restore: from get_language_model to get_model as in main

- feat(sdk)implement unified get_model() with auto-detection

BREAKING CHANGE: Removed get_language_model(), get_embedding_model(), and get_embedder(). Use get_model() instead which auto-detects model type from name or accepts explicit model_type parameter.

- Add BaseModel common base class for all model types
- Add ModelType enum (LANGUAGE, EMBEDDING, IMAGE)
- Implement \_classify_model() using litellm metadata + heuristics
- Create UNIFIED_MODEL_REGISTRY replacing separate registries
- Add @overload decorators for type safety
- Support both auto-detection and explicit model_type parameter
- Migrate to get_model() in entities and adaptive testing

* refactor(backend): migrate to unified get_model() with explicit model types

* test(sdk): rewrite model factory tests for unified get_model()

* docs: update model examples to use get_model() instead of get_embedder()

* refactor(backend): use DEFAULT_EMBEDDING_MODEL and positional get_model

- Use single DEFAULT_EMBEDDING_MODEL in services router and migration
- Call get_model(unified_string) instead of get_model(provider=...) in backend
- Document get_model first-arg provider/model_name resolution in SDK

* fix(tests): fix imports and signature

* fix(tests): resolve UnmappedClassError

* chore: formatting

* fix: remove 'rhesis' from EMBEDDING_PROVIDERS so that it lists only user-selectable providers

* docs: default should be Rhesis embedding model

* refactor(sdk): unify model defaults as provider/name (MODEL=provider/name)

* feat: add get_embedding_model(), get_language_model() and aliased get_embedder()

* tests: add tests for get_model() model_type classification

* fix: change from rhesis-default to rhesis-embedding for default embedding model name

* fix: change from 'llm' -> 'language'

- Fix test run metric filter and add duplicate for behaviors/metrics (#1347)

* fix(frontend): deduplicate metrics in test run filter

Metrics from multiple behaviors were shown as duplicates in the
"Failed Metrics" filter. Deduplicate using a Map keyed by metric
name and wire up the filter logic so selected metrics actually
filter the test results list.

- feat(frontend): add duplicate for behaviors and metrics

Add a duplicate button to behavior cards, behavior drawer,
metric cards, and the metric detail page. Copies are created
with an incrementing "(Copy N)" suffix via a shared utility.

- Add duplicate endpoint and fix endpoint creation (#1346)

* fix(backend): make test_endpoint stateless-aware

Add one-shot messages array construction to test_endpoint() so
stateless endpoints (with {{ messages }} in request_mapping) can
be tested before saving.

- feat(frontend): add duplicate endpoint button

Add a Duplicate button between Playground and Edit on the endpoint
detail screen. Creates a copy with "(copy)" suffix and navigates
to the new endpoint. Includes 10 tests covering the feature.

- feat(backend): auto-assign active status on endpoint creation

The create_endpoint router now assigns "Active" status when no
status_id is provided. Adds 4 integration tests verifying the
auto-assignment and explicit status preservation.

- fix(frontend): fix duplicate endpoint naming and add bulk duplicate

Fix copy naming to increment correctly (Copy) → (Copy 2) → (Copy 3).
Strip server-managed fields (nano_id, created_at, updated_at).
Add bulk duplicate button to endpoint list grid.

- fix(frontend): fix infinite loop in useFormChangeDetection

Remove initialData object reference from useEffect deps to prevent
re-render loop when parent creates a new object each render. Only
depend on the serialized initialDataString for stability.

- fix(backend): set null endpoint statuses to active

Add migration to update all endpoints with NULL status_id to the
Active status for the General entity type within their respective
organization, joining through type_lookup for correct scoping.

- fix(frontend): resolve @typescript-eslint/no-unused-vars warnings (#1304)

* fix(frontend): reduce lint warnings by 216

- Prefix 141 unused catch variables with underscore
- Update eslint config to ignore underscore-prefixed variables
- Allow console.warn and console.error in eslint config
- Replace @ts-ignore with @ts-expect-error
- Remove unnecessary ts-expect-error directive

Reduces warnings from 1143 to 927 while maintaining 0 TypeScript errors.

- fix(frontend): replace safe any types with unknown

* odata-filter.ts: 11 any → unknown for value parameters
* sources-client.ts: 1 Record<string, any> → Record<string, unknown>
* trace-utils.ts: 1 any[] → unknown[] for children type

- fix(frontend): remove debug console.log statements

Remove unnecessary debug logs that were causing no-console warnings:

- TrialDrawer.tsx: remove debug logs for data fetching
- models/page.tsx: remove model validation debug log
- usePlaygroundChat.ts: remove chat response debug logs
- WebSocketContext.tsx: remove visibility change log
- websocket/client.ts: remove connection lifecycle logs
- quick_start.ts: remove Quick Start mode debug logs

* fix(frontend): remove unused imports and prefix unused variables

- ActivityTimeline: remove unused icons and formatDistance
- DashboardKPIs: remove useRouter, prefix unused vars
- TestRunPerformance: remove unused Avatar and PersonIcon
- EndpointDetail: remove unused Snackbar and notification state
- EndpointForm: remove unused InfoIcon and CONNECTION_TYPES
- EndpointsGrid: prefix unused onboarding vars
- endpoints/page: remove unused useEffect import
- SourcePreviewClientWrapper: remove unused icons, fix catch vars
- knowledge/page: remove unused Box and CommentsWrapper
- KnowledgeClientWrapper: prefix unused vars
- MCPImportDialog: fix unused catch var and index
- MCPToolSelectorDialog: remove unused Dialog imports
- SourcesGrid: remove unused constants, fix unused index
- UploadSourceDialog: remove unused Chip, prefix unused func

* fix(frontend): cleanup unused vars in MCP components

- MCPConnectionDialog: fix unused event params, prefix notifications
- MCPProviderSelectionDialog: remove unused type import, prefix unused var

* fix(frontend): clean up unused imports and variables

- Remove unused Dialog-related imports from MetricsDirectoryTab
- Remove unused MUI imports from TeamMembersGrid and client-wrapper
- Remove unused getCsrfToken, UserCreate imports from OnboardingPageClient
- Remove unused MetricsResponse, ModelsResponse imports from api clients
- Remove unused API_ENDPOINTS, API_CONFIG, interface imports
- Prefix unused state variables with underscores
- Prefix unused catch block variables with underscores

* fix(frontend): remove unused imports from onboarding components

- Remove unused Typography, Stack imports
- Remove unused Box import from onboarding page
- Remove unused validateRequired import
- Prefix unused callback parameters with underscores

* fix(frontend): clean up unused imports and variables across components

- Remove unused MUI component imports (Box, Typography, Paper, Button, etc.)
- Remove unused icon imports (EditIcon, FolderIcon, PersonIcon, etc.)
- Prefix unused props and parameters with underscore (\_organizationId, \_onRefresh, etc.)
- Prefix unused catch block errors with underscore (\_error)
- Remove unused function definitions or prefix with underscore

Files cleaned up include: metrics, organizations, projects, tasks,
test-results, and test-runs components.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): clean up unused imports and variables in test-runs/test-sets

* Remove unused imports (TestSet, Endpoint, Button, Grid, Typography, etc.)
* Prefix unused callback parameters with underscore (\_index, \_reviewData, etc.)
* Prefix unused catch block errors with underscore (\_error, \_fetchError, etc.)
* Prefix unused functions with underscore (\_handleTestSaved)
* Prefix unused interface with underscore (\_PageProps)
* Remove unused useState import from TestSetWorkflowSection

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): clean up unused imports and variables in test-sets/tests

* Remove unused imports (useRef, useChartColors, Grid, FormControl, etc.)
* Prefix unused catch block errors with underscore (\_err, \_error)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- style(frontend): fix unused vars in test detail components

* Remove unused imports (Legend, TypeLookup, Paper, Typography, ArrowBackIcon,
  CommentsWrapper, FormHelperText, ListItemAvatar, ListItemText, useState,
  useEffect, useRef)
* Prefix intentionally unused variables with underscore (\_testId, \_key)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- style(frontend): fix unused vars in test results and test runs components

* Prefix unused variables with underscore (\_theme, \_getContextInfo, \_hasHumanReview)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- style(frontend): fix unused catch error variable in task detail page

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): resolve no-unused-vars warnings in test components

* Prefix intentionally unused variables with underscore
* Remove unused imports (Divider, Endpoint, FormHelperText, etc.)
* Remove unused functions (formatExecutionTime, truncateName)
* Fix destructured key variables in renderOption callbacks

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): resolve more no-unused-vars warnings

* Prefix unused theme/types/handleNewTest variables with underscore
* Remove unused Alert import from TestCharts
* Remove duplicate tagsClient declaration
* Fix key destructuring in renderOption callbacks

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): resolve additional no-unused-vars warnings

* Prefix unused variables: displayLegendLabel, responseLabel, requestTimestamp
* Prefix unused theme variables in TestDetailCharts
* Fix error variables in catch blocks for MultiTurnConfigFields

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): resolve no-unused-vars warnings in token and test components

* Remove unused useState import from TokenDisplay
* Prefix unused theme variable in TokensGrid
* Remove unused deletedToken variable in TokensPageClient
* Fix prevData and key variables in UpdateTest

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): resolve no-unused-vars warnings in test, trace, auth components

Remove unused imports and prefix intentionally unused variables with
underscores to fix @typescript-eslint/no-unused-vars warnings:

- test generation components
- trace viewer components
- auth and layout files

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): resolve no-unused-vars warnings in project, trace, auth, comment components

Remove unused imports and prefix intentionally unused variables with
underscores to fix @typescript-eslint/no-unused-vars warnings in:

- project creation components
- trace components
- auth components
- comment components
- common components (BaseDataGrid, BaseFreesoloAutocomplete)
- feedback API route

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): fix unused vars warnings in common components

* BaseFreesoloAutocomplete: prefix unused key with underscore
* BasePieChart: prefix unused innerRadius, index, variant with underscore
* BaseScatterChart: remove unused Legend, Cell imports, prefix unused vars
* BaseTable: prefix unused interface AddButtonProps with underscore
* BaseTag: remove unused InputProps, FormHelperText, prefix unused vars
* BaseWorkflowSection: remove unused MenuItem import

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): fix unused vars warnings in various components

* layout.tsx: prefix unused options param with underscore
* ConnectionDialog.tsx: prefix unused e param in onFocus
* ConversationHistory.tsx: prefix unused turnCriteriaFailed
* ErrorBoundary.tsx: prefix unused error and errorInfo in hook
* NotFoundAlert.tsx: prefix unused backLabel param
* ThemeProvider.tsx: prefix unused CssBaseline import
* TaskCreationDrawer.tsx: remove unused Button/CircularProgress, prefix unused user props
* TaskErrorBoundary.tsx: prefix unused error and errorInfo in componentDidCatch
* TaskItem.tsx: remove unused Link/formatDistanceToNow/TaskStatus/TaskPriority imports
* TasksSection.tsx: remove unused imports, prefix unused params
* TasksWrapper.tsx: prefix unused currentUserPicture
* test-templates.generated.ts: prefix unused iconMap
* useComments.ts: remove unused import types
* telemetry.ts: remove unused OpenTelemetry imports, prefix unused provider
* middleware.ts: prefix unused isSessionExpired
* client-factory.test.ts: remove unused client imports
* base-client.ts: remove unused PaginationMetadata import
* behavior-client.ts: prefix unused include param

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): fix more unused vars warnings

* BaseWorkflowSection.tsx: prefix unused entityId, statusReadOnly, InfoRow, key, error
* TasksAndCommentsWrapper.tsx: remove unused useEffect import
* TasksSection.tsx: prefix unused handleDeleteTask
* middleware.ts: prefix unused error in catch blocks
* base-client.ts: prefix unused error and parseError in catch blocks
* test-configuration.ts: remove unused TypeLookup import
* test-results.ts: remove unused Behavior import
* test-run.ts: remove unused Endpoint and TestSet imports

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): fix remaining unused vars warnings

* tasks/[identifier]/page.tsx: prefix unused value in renderValue
* LatestTestRunsChart.tsx: prefix unused name, props, payload in formatter
* TestSetDetailsSection.tsx: prefix unused error in catch blocks
* TestSetWorkflowSection.tsx: prefix unused destructured fields (id, status_details, etc)
* TestGenerationFlow.tsx: prefix unused setTestType, index, ratedSamples
* ManualTestWriter.tsx: prefix unused handleImport
* SpanTreeView.tsx: prefix unused index in map
* TracesClient.tsx: prefix unused handleRefresh
* BaseLineChart.tsx: prefix unused height prop
* OnboardingContext.tsx: prefix unused element param
* base-client.ts: prefix remaining parseError in catch block

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- docs(frontend): add cursor rules for avoiding unused variables

Add .cursorrules file with guidelines for avoiding @typescript-eslint/no-unused-vars warnings, including patterns for:

- Unused imports (remove them)
- Unused function parameters (prefix with underscore)
- Unused catch block errors
- Unused destructured variables
- Unused useState setters
- Unused component props
- Unused map/filter callback parameters

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- docs: add frontend typescript linting rules to .cursor/rules

Move cursor rules for avoiding @typescript-eslint/no-unused-vars warnings
to the project-wide .cursor/rules directory with proper glob patterns
for frontend TypeScript files.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- docs: set alwaysApply: true for frontend linting rules

Ensure the frontend TypeScript linting rules are always applied
when developing, matching the pattern used by other rules like
python-linting.mdc.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(frontend): resolve duplicate import and console statement errors

* Combine duplicate @mui/material imports in MarkdownContent.tsx
* Remove console.log in telemetry.ts (telemetry is disabled)
* Use explicit console.warn/error calls in base-client.ts

- fix(frontend): resolve react/no-array-index-key in onboarding and EntityCard

* Add unique id field to invite objects in onboarding flow
* Use invite.id instead of array index as React key
* Use first chip key as section key fallback in EntityCard

- fix(frontend): resolve more react/no-array-index-key errors

* Use composite keys (role/name + index) in ChatPreview and ContextPreview
* Use criterion name in ConversationHistory
* Use child key with fallback in BaseChartsGrid

- fix(frontend): properly place eslint-disable comments for array index keys

Move eslint-disable-next-line comments to correct positions inside map
callbacks where the key attribute is defined

- fix(frontend): resolve all react/no-array-index-key errors

Add file-level eslint-disable comments for components that use array
index as React keys for display-only content that won't be reordered:

- Metrics pages (evaluation steps display)
- Test detail components (parsed text, charts, data grids)
- Team invite form (dynamic form fields)
- Trace span details
- Common base components (charts, tables, grids)

* style(frontend): apply prettier formatting

* docs: expand frontend linting rules with additional patterns

Add guidance for:

- react/no-array-index-key: when to use unique IDs vs eslint-disable
- no-duplicate-imports: combining imports from same module
- no-console: using console.warn/error only
- Running formatter before committing

* fix(frontend): resolve no-non-null-assertion warnings

- Replace non-null assertions with type guards in filter callbacks
- Add explicit null checks before using potentially null values
- Use optional chaining where appropriate
- Capture variables before async closures to enable type narrowing
- Fix eslint-disable comment placement for array index keys

* fix(frontend): resolve react-hooks/exhaustive-deps warnings

Add missing dependencies to useEffect, useCallback, and useMemo hooks:

- Wrap async functions in useCallback for stable references
- Add missing state variables and callbacks to dependency arrays
- Extract complex expressions from dependency arrays
- Add eslint-disable comments where intentional (sync effects)

* fix(frontend): resolve typescript errors, unused vars, and lint warnings

- Fix TypeScript compilation errors caused by `unknown` types leaking
  into JSX children (e.g. Record<string, unknown> metadata accessed
  via short-circuit && in Grid container children)
- Exclude e2e/ and playwright.config.ts from tsconfig to avoid
  missing @playwright/test module errors
- Fix unused variable warnings by prefixing with \_ or removing imports
- Fix non-null assertion warnings in ConnectionDialog
- Fix react-hooks/exhaustive-deps warnings
- Replace console.log with console.error/warn or remove in TrialDrawer
- Add testRunId to RerunConfig interface
- Properly type-narrow date fields and environment attributes

* fix(frontend): replace all explicit any with proper types

Systematically replace 342 `any` usages across 118 frontend files
with proper TypeScript types:

- Record<string, any> -> Record<string, unknown> in interfaces and clients
- catch (error: any) -> catch (error: unknown) with instanceof narrowing
- MUI callback params typed with GridRenderCellParams, GridRowParams, etc.
- as any assertions replaced with proper type assertions
- Promise<any> return types replaced with typed interfaces
- sx?: any -> SxProps<Theme>
- Recharts formatters typed with (value: string | number)
- eslint-disable added to test files for mock-related any usage

Both tsc --noEmit and npm run lint now pass with zero errors
and zero warnings.

- docs: update frontend linting rules with no-explicit-any guidance

Add comprehensive sections for no-explicit-any patterns, unknown
type handling in JSX, non-null assertions, and React hooks
exhaustive deps. Expand best practices from 5 to 10 items.
Set alwaysApply to false with targeted description.

- fix(frontend): resolve infinite re-render loop on dashboard

Memoize onLoadComplete callbacks with useCallback to prevent
new function references on every render, which caused useEffect
in DashboardKPIs, TestRunPerformance, and ActivityTimeline to
re-trigger infinitely.

- refactor(frontend): rename middleware to proxy for Next.js 16

Next.js 16 deprecated the "middleware" file convention in favor of
"proxy". The API surface (NextRequest, NextResponse, config) is
identical — only the file and function names changed.

- build(frontend): update next.js to 16.1.6 and clean up config

* Update Next.js from 16.0.10 to 16.1.6, fixing the stale
  baseline-browser-mapping data warning bundled in the old version
* Remove experimental optimizePackageImports since the heavy
  barrel-export libraries are already optimized by Next.js by default
* Remove unnecessary baseline-browser-mapping direct devDependency

- fix(frontend): add keys to navigation icon elements

Add unique key props to all icon elements in the navigation items
to resolve React "missing key" warning from MuiListItemIconRoot.

- style(frontend): format code with prettier

Run prettier --write on 54 files that had formatting issues.
Also fix test mocks to use stable notification object references,
preventing unstable useCallback/useEffect dependencies.

- test(frontend): add tests for date and import-error-utils

Add unit tests for formatDate and getImportErrorMessage to meet the
17% function coverage threshold (was 16.76%, needed 2 more functions).

- test(frontend): add tests for timelineUtils chart helpers

Add 13 tests covering all 5 pure utility functions in timelineUtils.ts
(formatTimelineDate, transformTimelineData, extractOverallData,
createMetricExtractor, generateMockTimelineData). Also update .gitignore
to allow source files under the test-results app route.

- test(frontend): add tests for components and extend odata-filter coverage

Add tests for TestRunStatus, UserAvatar, NotFoundAlert, and AppVersion
components. Extend odata-filter tests to cover all domain-specific quick
filter and combine functions (tasks, tests, sources, test runs, test sets).
Increases function coverage from 16.76% to 19.49%.

- style(frontend): format test files and chart components

- fix(frontend): add missing required props in NotFoundAlert test mock

---

Co-authored-by: Claude Opus 4.5 <noreply@anthropic.com>

- refactor(tests): extract frontend E2E docker setup into compose file (#1335)

Create tests/docker-compose.frontend.yml with dedicated services
(frontend-test-postgres:14001, frontend-test-redis:14002,
frontend-test-backend:14003) so the E2E workflow no longer creates
inline .env files or drives docker compose directly.

Add docker-up/docker-down/docker-clean/test-e2e Make targets to
apps/frontend/Makefile. Simplify the GitHub workflow to delegate
to these targets.

- Adaptive testing (#1301)

* feat: adaptive testing first commit

* docs(sdk): add batch processing documentation for models

Document the generate_batch method for LiteLLM-based providers,
including examples for basic batch generation, structured output
with schemas, and multiple completions per prompt.

- feat(sdk): integrate environment variable support for API keys

* Added dotenv support to load environment variables from a .env file.
* Updated API key retrieval in rhesis_model and rhesis_scorer functions to use os.getenv for better security and flexibility.
* This change allows for easier configuration management and enhances the adaptability of the SDK in different environments.

- feat(sdk): update OpenAI generator to use new model initialization

* Changed default model to "gpt-4.1-mini" and updated constructor parameters for clarity.
* Replaced batch_completion with model.generate_batch for improved suggestion generation.
* Enhanced error messaging for empty prompts and improved prompt string formatting.
* Integrated model initialization using get_model for better modularity.

- refactor: improve formating of adaptive testing

- feat(sdk): add generate_batch method to BaseLLM class

* Introduced the generate_batch method for processing multiple prompts, returning a list of strings or dicts based on provided schemas.
* Updated the docstring for the run method to reflect the potential return types.

- feat(sdk): refactor rhesis_model and rhesis_scorer to use generate_batch

* Replaced litellm's batch_completion with the new generate_batch method for improved performance and modularity.
* Introduced a shared model instance for better resource management.
* Updated prompt preparation and response handling to align with the new model structure.

- refactor(sdk): rename rhesis_model to llm_endpoint for clarity

* Updated function name from rhesis_model to llm_endpoint to better reflect its purpose in classifying sentence pairs.
* Adjusted references in the TestTreeBrowser class to use the new function name.

- delete: remove obsolete sequence classification tests CSV file

- refactor(sdk): update llm_endpoint to return raw model results

* Modified llm_endpoint to return the raw results from the model's generate_batch method instead of structured labels.
* Adjusted prompt formatting to reflect the new purpose of the function as a chatbot response generator.

- delete: remove sequence classification tests CSV file

- refactor(sdk): update scoring and prompt generation for adaptive testing

* Enhanced the scoring criteria in rhesis_scorer to include specific rule violations for bot responses.
* Revised prompt instructions in OpenAI generator to clarify the task of generating tests without including the topic.

- refactor(sdk): enhance TestTree and TestTreeBrowser initialization

* Updated TestTree and TestTreeBrowser classes to accept new parameters: generator, endpoint, and metrics for improved flexibility.
* Replaced deprecated scorer parameter with metrics for better clarity and functionality.
* Adjusted prompt generation instructions in the OpenAI generator to differentiate between test inputs and subtopic names.

- refactor(sdk): streamline TestTreeBrowser generator handling

* Removed the active_generator parameter and refactored the TestTreeBrowser to use a single generator instance for improved clarity.
* Updated the initialization process to directly handle TestTree instances and ensure proper embedding calculations.
* Simplified the suggestion generation logic by eliminating the need for multiple generator references.

- refactor(sdk): clean up adaptive testing code and remove deprecated parameters

* Removed unused uuid import and default_generators variable for better code clarity.
* Simplified the TestTreeBrowser initialization by eliminating deprecated scorer and drop_inactive_score_columns parameters.
* Updated generator call signatures to remove unnecessary parameters and improve consistency.
* Cleaned up comments and unused code sections across various files to enhance maintainability.

- feat(sdk): introduce embedding functionality and embedder factory

* Added BaseEmbedder class for embedding models with methods for generating single and batch embeddings.
* Implemented LiteLLMEmbedder and OpenAIEmbedder classes for specific embedding model support.
* Enhanced factory functions to create embedder instances with smart defaults and error handling.
* Updated documentation to reflect new embedding capabilities and usage examples.

- refactor(sdk): remove global embedder state in adaptive testing

Pass embedder explicitly through class hierarchy instead of using
module-level globals. The embedder is now configured via adapt()
and stored on TestTreeBrowser instance.

- Replace \_embed() global with embed_with_cache(embedder, strings)
- Add embedder parameter to adapt() and TestTreeBrowser
- Add embed_fn parameter to PromptBuilder.**call**()
- Update \_cache_embeddings() to require embedder parameter
- Remove compute_embeddings from TestTree constructor
- Export get_embedder from rhesis.sdk.models

* refactor(sdk): remove description field from TestTree and TestTreeBrowser

- Eliminated the 'description' field from the TestTree and TestTreeBrowser classes to streamline data handling.
- Updated related methods and generator signatures to reflect the removal of the description parameter.
- Cleaned up unused code and comments for improved clarity and maintainability.

* refactor(sdk): update TestTreeBrowser to use NaN for model scores and add to_eval column

- Replaced "**TOEVAL**" placeholder with NaN for model scores in TestTreeBrowser.
- Introduced a new "to_eval" column to track evaluation status of tests.
- Cleaned up related logic to ensure proper handling of evaluation conditions.
- Removed unused image handling code from the Row component for improved clarity.
- Streamlined utility functions by removing deprecated image caching logic.

* fix(test): use tmpfs for ephemeral test containers

Use RAM-based storage for postgres and redis in integration tests to
prevent stale volume data from causing database initialization issues.
Also rename containers to rhesis-\*-sdk-test for clarity.

- feat(sdk): add TestTree.to_test_set() for backend persistence

Add method to convert adaptive TestTree to SDK TestSet entity for
syncing with the Rhesis backend. Also add push validation to ensure
required fields are set before API calls.

- test(sdk): add unit tests for TestTree functionality

Add comprehensive tests for TestTree operations including to_test_set
conversion, topic handling, and edge cases.

- refactor(sdk): rename suggestion_thread_budget to prompt_variants in TestTree and TestTreeBrowser

* Updated parameter names for clarity, replacing suggestion_thread_budget with prompt_variants to better reflect its purpose.
* Adjusted related logic in TestTreeBrowser to utilize prompt_variants for generating diverse test prompts.
* Enhanced documentation to describe the new prompt_variants parameter and its functionality.

- feat(sdk): add validation for required fields in Test and TestSet

* Add \_push_required_fields to Test entity (category, behavior)
* Validate each test has required fields when pushing TestSet
* Add unit tests for TestSet push validation

- feat(sdk): add behavior and category fields to TestTree tests

* Introduced 'behavior' and 'category' fields with the value "Adaptive Testing" for tests created in TestTree.
* Enhanced test metadata to improve categorization and functionality within adaptive testing framework.

- feat(sdk): enhance insurance chatbot prompts and add output regeneration feature

* Updated the llm_endpoint prompts to include specific insurance offerings and guidelines for user interactions.
* Modified the rhesis_scorer prompts to clarify the context of the insurance chatbot and its compliance rules.
* Introduced a regenerate_outputs parameter in TestTree and TestTreeBrowser to allow for re-evaluation and fresh output generation from the endpoint.
* Ensured that regenerating outputs also triggers score recomputation for consistency.

- refactor(sdk): remove llm_endpoint function and update adapt method signatures

* Removed the llm_endpoint function to streamline the codebase and focus on the TestTree functionality.
* Updated the adapt method in TestTree to include type hints for parameters, enhancing code clarity and maintainability.
* Ensured that the adapt method's signature aligns with the latest design for better integration with the adaptive testing framework.

- refactor(sdk): clean up \_test_tree_browser.py by removing unused code and imports

* Removed the load_dotenv function and associated model initialization logic to simplify the codebase.
* Eliminated the rhesis_scorer function, which was previously responsible for scoring chatbot responses, to focus on core functionality.
* Streamlined imports and cleaned up commented-out code for better readability and maintainability.

- refactor(sdk): update embedder parameter documentation in TestTree

* Enhanced the documentation for the embedder parameter to specify required properties and method signatures for better clarity.
* Clarified the default behavior when no embedder is provided, ensuring users understand the fallback to OpenAITextEmbedding.

- refactor(sdk): update embedder handling in TestTreeBrowser and related classes

* Refactored the embedder initialization in TestTreeBrowser to utilize an EmbedderAdapter for better caching compatibility.
* Updated the embedder parameter in TestTree to require an instance of BaseEmbedder, enhancing type safety and clarity.
* Removed the OpenAITextEmbedding class and replaced it with a call to get_embedder for default embedding, streamlining the embedder setup process.
* Improved documentation for embedder usage and behavior in both TestTree and TestTreeBrowser.

- refactor(sdk): remove unused str property from TestTree

* Eliminated the str property from TestTree to streamline the code and improve clarity.
* This change helps focus on the essential functionality of the TestTree class.

- feat(sdk): enhance package management and documentation in adaptive testing

* Added new packages: `aiohttp-security`, `aiohttp-session`, `joblib`, `profanity`, and `threadpoolctl` to improve functionality and security in the adaptive testing framework.
* Updated the `__all__` variable in `__init__.py` to include key components for better module export.
* Improved docstring formatting in `_prompt_builder.py`, `_server.py`, and `_test_tree_browser.py` for enhanced readability and clarity.
* Refactored comments in various files to improve code maintainability and understanding.
* Ensured consistent import formatting across files to adhere to style guidelines.

- refactor(sdk): enhance TestTree and generator integration

* Added BaseLLM import to support flexible LLM integration in adaptive testing.
* Introduced LLMGenerator class to allow any BaseLLM instance for test generation, enhancing compatibility with various LLM providers.
* Improved docstring formatting and clarity in TestTree and generator classes.
* Streamlined comments and code for better readability and maintainability.

- refactor(sdk): improve type hints and remove unused templatize function in TestTreeBrowser

* Enhanced type hints for parameters in the TestTreeBrowser constructor to improve clarity and type safety.
* Removed the unused templatize function and associated commented-out code to streamline the codebase and focus on essential functionality.
* Updated import statements for better organization and clarity.

- refactor(sdk): streamline TestTreeBrowser and enhance type safety

* Improved type hints in the TestTreeBrowser class for better clarity and type safety.
* Removed the unused templatize function and cleaned up associated commented-out code to focus on essential functionality.
* Organized import statements for improved clarity and maintainability.

- refactor(sdk): enhance TestTreeBrowser and TestTree integration

* Updated TestTreeBrowser to utilize new functions for score removal and evaluation status setting, improving code clarity and maintainability.
* Introduced a templatize method for standardizing template expansions, enhancing functionality.
* Refactored TestTree to support a more structured approach with TestTreeNode and TestTreeData, improving data handling and organization.
* Added validation for topic encoding in TestTreeNode to ensure proper formatting.
* Implemented new utility functions in tree_data_ops for managing evaluation states and retrieving evaluation IDs, streamlining operations on test tree data.

- refactor(sdk): enhance TestTreeBrowser and schemas for improved data handling

* Updated TestTreeBrowser to utilize TestTreeData and TestTreeNode for better data management and clarity.
* Refactored the way test outputs and scores are handled, replacing direct DataFrame manipulations with structured node updates.
* Enhanced TestTreeData to support item retrieval and assignment by both integer index and string ID, improving usability.
* Added tests to validate the new item access and assignment functionalities in TestTreeData, ensuring robustness.

- refactor(sdk): enhance TestTreeBrowser and schemas for improved data retrieval

* Updated TestTreeBrowser to access test data through structured TestTreeData and TestTreeNode, improving clarity and maintainability.
* Refactored filtering logic to utilize attributes directly instead of dictionary keys for better performance.
* Added methods in TestTreeData to retrieve topic markers and test nodes, enhancing data management capabilities.
* Introduced unit tests for the new retrieval methods, ensuring correctness and reliability.

- refactor(sdk): simplify TestTreeBrowser and TestTree structure

* Removed the auto_save parameter from TestTreeBrowser and TestTree constructors to streamline functionality.
* Updated the logic for adding new topics and tests to utilize TestTreeNode for improved clarity and maintainability.
* Enhanced the refresh interface logic by removing unnecessary auto-save calls, focusing on essential updates.
* Adjusted the mode handling in the browser component for better user experience and clarity.

- refactor(sdk): optimize TestTreeBrowser for node management and topic updates

* Simplified topic assignment and deletion logic by directly manipulating TestTreeNode attributes instead of using DataFrame operations.
* Enhanced the handling of test updates and score computations to utilize structured node access, improving clarity and maintainability.
* Streamlined the suggestion generation process by creating new TestTreeNode instances, ensuring consistent data handling across the browser component.

- refactor(sdk): streamline \_compute_embeddings_and_scores method in TestTreeBrowser

* Updated the \_compute_embeddings_and_scores method to accept only necessary parameters, enhancing clarity and reducing complexity.
* Adjusted calls to this method throughout the TestTreeBrowser class to align with the new signature, improving maintainability.
* Improved logging to reflect the new structure, ensuring better debugging and tracking of score computations.

- refactor(sdk): remove unused tree_data_ops functions and simplify eval ID retrieval

* Deleted the tree_data_ops module as its functions were no longer needed.
* Updated TestTreeBrowser to directly retrieve evaluation IDs from test tree nodes, enhancing clarity and reducing dependency on external functions.
* Improved the overall structure of the code by streamlining the evaluation ID logic.

- refactor(sdk): optimize prompt building and test tree handling

* Replaced DataFrame operations with direct node attribute access in the PromptBuilder class for improved performance and clarity.
* Simplified the logic for topic scaling and filtering by utilizing structured node access, enhancing maintainability.
* Removed unused hidden scaling logic, streamlining the prompt generation process.
* Updated the TestTreeBrowser to use set comprehensions for duplicate test detection, improving efficiency and readability.

- refactor(sdk): linting errors fix

- refactor(sdk): simplify TestTree class and remove unused methods

* Removed the deduplicate method and related commented-out code to streamline the TestTree class.
* Updated the topic filtering logic to return a new TestTree instance instead of a DataFrame, enhancing clarity and maintainability.
* Cleaned up unused methods and comments to improve overall code readability.

- refactor(sdk): improve topic handling and evaluation logic in TestTreeBrowser

* Enhanced topic filtering to include all nodes at the root level when no specific topic is provided.
* Updated child topic name extraction to handle cases where the topic is empty, ensuring correct data representation.
* Refined score retrieval logic to skip topic markers, preventing unnecessary evaluations and improving performance.
* Adjusted sorting logic to prioritize new topics correctly, enhancing user experience in the test tree browser.

- refactor(sdk): enhance topic management and add utility methods in TestTreeData

* Updated TestTreeBrowser to dynamically generate new topic names based on the current topic, improving usability.
* Added methods in TestTreeData to check for direct tests and subtopics, enhancing topic management capabilities.
* Ensured topic markers are not evaluated during topic creation, streamlining the interface refresh process.

- refactor(sdk): streamline TestTreeBrowser and enhance TestTreeData methods

* Removed unused pandas dependency and optimized score resetting logic in TestTreeBrowser to directly manipulate node attributes.
* Updated the suggestion generation process to consistently use a node-based approach, improving clarity and maintainability.
* Added append and remove methods in TestTreeData for better node management, enhancing the overall functionality of the test tree structure.

- next

- sdf

- refactor(sdk): enhance topic creation and management in TestTreeBrowser

* Updated the logic for adding new topics to utilize the topic tree structure, improving clarity and maintainability.
* Refined the move functionality to handle both individual tests and entire topics more effectively, enhancing user experience.
* Improved the deletion process to ensure proper handling of both test IDs and topic paths, streamlining the interface refresh.
* Adjusted the method for retrieving topic marker IDs to work with topic paths, enhancing consistency across the codebase.

- refactor(sdk): simplify child topic handling in TestTreeBrowser

* Introduced a new method, \_build_topic_children, to streamline the process of building UI data for topic children, enhancing code clarity and maintainability.
* Removed redundant logic for creating children and integrated it into the new method, improving overall efficiency in the interface refresh process.
* Updated the handling of suggestions to utilize the new method, ensuring consistent data representation across the test tree structure.

- next

- refactor(sdk): enhance metadata handling in TestTree

* Updated the TestTree class to store all relevant node fields (tree_id, output, label, labeler, model_score) in metadata for complete round-trip support.
* Adjusted the prompt creation and metadata extraction processes to ensure backward compatibility while maintaining clarity.
* Simplified the return structure of TestTreeData to improve readability and maintainability.

- next

- next

- next

- feat(sdk): add TestSet.pull() with tests and fetch_tests() method

* Add fetch_tests() method to TestSet for fetching associated tests
* Override pull() to include tests by default (configurable via include_tests param)
* Add field validators to Test for handling expanded API responses
* Add integration tests for TestSet push/pull functionality

- feat(sdk): add model_validator to Test for metadata mapping

* Introduced a model_validator to the Test class to map 'test_metadata' from backend responses to 'metadata' for consistency.
* Ensured that 'test_metadata' is removed if 'metadata' already exists, improving data handling in the SDK.

- feat(sdk): update package dependencies and remove obsolete tests

* Added new packages: aiohttp-security, aiohttp-session, joblib, and profanity with their respective versions and sources.
* Updated optional dependencies for adaptive testing to include new packages.
* Removed obsolete test for handling special characters in topics and content from the integration tests.

- refactor(sdk): update TestTree to include topic markers in test sets

* Modified TestTree to allow topic markers to be included in the test set, enhancing the round-trip functionality.
* Adjusted the logic to skip topic markers only when they lack prompts, ensuring they are processed correctly.
* Updated integration tests to verify that topic markers are now included in the restored test set, reflecting the changes in behavior.

- feat(sdk): add validation method to TestTree for topic marker checks

* Introduced a `validate` method in the TestTree class to ensure that all topics used by tests have corresponding topic_marker nodes, including checks for parent topics in the hierarchy.
* The method returns a dictionary with validation results, including lists of missing markers and topics with tests and markers.
* Added comprehensive unit tests to cover various scenarios, including valid trees, trees missing markers, and empty trees, ensuring robust validation functionality.

- feat(test-explorer): add Test Explorer feature with adaptive testing support

* Introduced a new "Test Explorer" page and layout for exploring test sets configured for adaptive testing.
* Implemented functionality to fetch and display adaptive test sets, including detailed views for individual test sets.
* Added components for displaying adaptive tests in a grid format and a topic tree for better navigation.
* Enhanced error handling for loading states and improved user experience with loading indicators and informative messages.
* Created a detailed view for individual tests, showcasing their input, output, score, and associated topics.

- refactor(sdk): move validate method from TestTree to TestTreeData

Move the validate() implementation to TestTreeData and have TestTree
delegate to it. This prepares for TestTree wrapper removal. Tests updated
to test TestTreeData.validate() directly.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add drag-and-drop to move tests between topics

* Add drag functionality to test rows in AdaptiveTestsGrid
* Add drop targets on topic tree nodes with visual feedback
* Implement getOrCreateTopic in TopicClient using $filter
* Update test topic via API when dropped on new topic
* Show loading indicator and success/error snackbar feedback

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add AddTestDialog component for creating/editing tests

* Support both 'add' and 'edit' modes with initialData prop
* Pre-populate topic field from selected topic
* Validate required fields (input, topic)
* Export TestFormData interface for type safety

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add edit and delete actions to tests grid

* Add onEdit and onDelete callback props
* Add Actions column with edit and delete icon buttons
* Export AdaptiveTest interface for reuse

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add TopicDialog component for creating/renaming topics

* Support 'create' and 'rename' modes
* Show parent path when creating subtopics
* Validate topic name (required, no slashes)
* Export TopicFormData interface

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add DeleteTopicDialog with impact summary

* Show warning about affected tests and child topics
* Display where items will be moved (parent topic)
* Confirmation dialog with loading state

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add topic CRUD actions to tree view

* Add right-click context menu with create/rename/delete actions
* Add 'Create Topic' button that creates subtopic when topic selected
* Support ApiTopic prop for showing topics with zero tests
* Export TopicAction and ApiTopic interfaces
* Consistent icon colors using text.secondary

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): implement full CRUD for tests and topics

Tests:

- Add test creation via bulk API with topic assignment
- Edit test dialog with pre-populated data
- Delete test with confirmation dialog
- Handle 410 errors for deleted tests gracefully

Topics:

- Create topics/subtopics under selected topic
- Rename topics with cascading updates to tests and children
- Delete topics with test migration to parent
- Track newly created topics in local state

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): pass testSetId and derive topics from test set

* Pass testSetId to AdaptiveTestsExplorer for test creation
* Derive topics from tests in current test set only
* Remove global topic fetch to avoid showing unrelated topics

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- docs(test-explorer): add backend requirements for topic operations

Document proposed backend endpoints to move topic CRUD operations
from frontend to backend for better efficiency:

- Rename topic with cascading updates
- Delete topic with test migration
- Move topic between parents
- Bulk move tests
- Get topic tree with counts

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- fix(test-explorer): filter tests by exact topic match only

Show only tests that belong directly to the selected topic,
excluding tests from child topics.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add clickable breadcrumb navigation for topics

* Split topic path into clickable segments
* Click any segment to navigate to that topic level
* "All Tests" link to clear selection
* Current topic shown as non-clickable text

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): show direct and children test counts as two chips

* First chip: direct test count in this topic
* Second chip: "+N" for tests in child topics (smaller, muted)
* Second chip only appears when children have tests

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- feat(test-explorer): add AdaptiveTestSetDrawer for creating and editing test sets

* Introduced AdaptiveTestSetDrawer component for managing test set details
* Integrated drawer into TestExplorerGrid for new test set creation and editing
* Implemented functionality for fetching test set types and handling save operations
* Added delete confirmation modal for selected test sets with notifications

- fix(tests): update topic formatting and assertions in test cases

* Removed leading slashes from topic strings in TestTreeNode instances for consistency.
* Updated assertions in test cases to reflect the new topic format.
* Adjusted test data to ensure correct validation of topic markers and test nodes.

- feat(sdk): add CRUD operations for tests and improve topic deletion

* Add Literal type for TestTreeNode.label field ("", "topic_marker", "pass", "fail")
* Add add_test(), update_test(), delete_test() methods to TestTreeData
* Automatically create topic markers when adding/updating tests
* Change TopicTree.delete() to move tests to parent by default instead of deleting
* Remove deprecated append() and remove() methods from TestTreeData

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- refactor(schemas): rename create method to add_topic for clarity

* Updated the method name from create() to add_topic() in TopicTree class to better reflect its functionality of adding a new topic.

- refactor(schemas): rename Topic to TopicNode for clarity

* Updated the Topic class to TopicNode across the codebase to better reflect its purpose in representing hierarchical topics.
* Adjusted related methods and imports to ensure consistency with the new naming convention.
* Modified tests to accommodate the changes in the Topic class structure.

- fix(sdk): preserve test tree order in TestSet round-trip

- feat(backend): add adaptive testing API endpoints and service

* Add adaptive testing router, schemas, and service
* Fix test_metadata field mapping (not metadata)
* Fix topic relationship access (use topic.name)
* Use dictionaries instead of anonymous classes for CRUD
* Add frontend API client for adaptive testing

- refactor(frontend): remove unused columns from test explorer grid

Remove categories, comments, tasks, tags, and type columns to simplify
the test explorer view.

- refactor(sdk): remove profanity filter from LLMGenerator

Updated the LLMGenerator class to remove the default profanity filter, allowing for an optional filter parameter instead. This change simplifies the generator's configuration and enhances flexibility in text generation.

- refactor(sdk): improve node kwargs construction in TestTree

Updated the logic for building node kwargs in the TestTree class to prioritize using the test.id (database ID) when available, falling back to the tree_id from metadata if not. This change enhances the clarity and reliability of node identification in the adaptive testing framework.

- refactor(backend): remove adaptive testing router, schemas, and service

* Deleted the adaptive testing router, schemas, and service files to streamline the codebase.
* Updated imports and exports in the main router to reflect the removal of adaptive testing components.

- refactor(sdk): remove profanity dependency from adaptive testing

Eliminated the profanity package from the adaptive testing dependencies in pyproject.toml to streamline the project and enhance flexibility in text generation.

- refactor(sdk): simplify test tree processing in TestTree

Removed the order_index variable from the TestTree class to streamline the processing of test nodes. Updated the logic to directly iterate over the tests without preserving order, enhancing code clarity and maintainability.

- feat(sdk): simplify adaptive testing topics and test tree id handling

- feat(backend): add adaptive testing endpoints and service

Re-add adaptive testing router with endpoints for listing adaptive
test sets, fetching full tree, tests-only, and topics-only views.
Includes service layer that converts backend Test models into SDK
TestTreeData structures.

- test(backend): add adaptive testing integration tests

Add route and service integration tests covering tree nodes, tests-only,
topics-only, and list endpoints with pagination, sorting, auth, and 404
handling.

- chore(backend): reduce log noise during tests

Set default LOG_LEVEL to WARNING in test conftest and comment out
verbose soft delete debug log for queries with LIMIT/OFFSET.

- fix(backend): add adaptive testing to token-enabled routes

Allow Bearer token authentication for /adaptive_testing/ endpoints,
required for frontend server-side rendering.

- feat(frontend): add adaptive testing pages and navigation

Add adaptive testing section to the frontend:

- Navigation item with AccountTreeIcon
- List page showing adaptive test sets
- Detail page with tree view for individual test sets
- API client methods for listing test sets and fetching trees
- Fix endpoint path to use underscores matching backend routes

* refactor(frontend): remove test explorer feature

Replaced by the adaptive testing section. Removes all test explorer
pages, components, and navigation entry.

- fix(sdk): fix get_all_parents returning strings instead of TopicNodes

The method was appending parent_path strings and reassigning them to
current, causing an AttributeError on the next iteration. Now creates
proper TopicNode instances at each level.

- feat(backend): implement create_topic_node service

Adds a service function that creates topic marker nodes in a test set,
automatically ensuring all ancestor topic markers exist for a valid
tree hierarchy. Uses TopicNode.get_all_parents() from the SDK.

- feat: add create topic endpoint and UI button

Add POST /adaptive_testing/{id}/topics endpoint that delegates to
create_topic_node. Wire up an "Add Topic" dialog in the frontend
tree panel so users can create topics from the UI.

- feat: add create test endpoint and UI

Add POST /{id}/tests endpoint, create_test_node service,
AddTestDialog frontend component, and remove topic/labeler
columns from the tests table. New tests are always created
without a label.

- fix(frontend): simplify test filtering logic in AdaptiveTestingDetail component

Refactor the filtering logic to only check for exact matches with the selected topic, removing the descendant topic matching. This change streamlines the code and improves clarity.

- feat: add update test endpoint and edit dialog

Add update_test_node service, PUT /{id}/tests/{test_id}
endpoint, and EditTestDialog frontend component. Also add
model_score support to test creation. Editable fields:
input, output, label, topic, model_score.

- feat(frontend): add drag-and-drop tests to topics

Enable dragging test rows from the DataGrid onto topic
tree nodes to reassign a test's topic. Uses native HTML5
Drag and Drop API with no new dependencies.

- feat: add delete test endpoint and confirmation dialog

Add delete_test_node service, DELETE endpoint, and
frontend delete button with confirmation dialog.

- feat: add update topic endpoint with rename support

Add PUT /adaptive_testing/{id}/topics/{path} endpoint that renames
a topic's current level name and cascades to all children and tests.

- feat(adaptive-testing): add create adaptive test set endpoint and UI

- fix(adaptive-testing): allow adding test without topic

- fix(frontend): allow creating topic when no topics in adaptive testing

- feat(adaptive-testing): add generate outputs backend

* Add generate_outputs_for_tests service to invoke endpoint per test
* Add POST generate-outputs route and request/response schemas
* Use get_endpoint_service() for endpoint invocation

- test(adaptive-testing): add tests for generate outputs

* Service tests for generate_outputs_for_tests (mock get_endpoint_service)
* Route tests for POST generate-outputs

- feat(adaptive-testing): add Generate outputs UI and improve Add/Edit test form

* Add generateOutputs API client and types
* Add Generate outputs dialog with endpoint picker and submit flow
* Rename Expected Output to Output (optional) with helper placeholder
* Remove Label field from Edit Test dialog

- feat(backend): add topic and include_subtopics to generate outputs

- feat(frontend): add topic selection and generate outputs button next to table

- refactor(frontend): remove Generate outputs button from AdaptiveTestingDetail component

- feat(frontend): add endpoint selection for output generation in AdaptiveTestingDetail component

* Introduced a new state for managing the selected endpoint for output generation.
* Added an Autocomplete component for users to select an endpoint above the Tree View/List View.
* Updated the useEffect to load endpoints on component mount instead of dialog open.
* Ensured selected endpoint is set when generating outputs.

- fix(frontend): ensure InputLabel shrinks for topic selection in AdaptiveTestingDetail component

* Added InputLabelProps with shrink set to true for both AddTestDialog and EditTestDialog to improve UI consistency.

- feat(adaptive-testing): implement delete topic functionality

* Added a new endpoint to delete topics from the adaptive testing tree, including handling of subtopics and associated tests.
* Implemented the `remove_topic_node` service to manage topic deletions and ensure tests are moved to the parent topic.
* Updated the frontend to include a delete button for topics, along with a confirmation dialog for user actions.
* Added integration tests for the delete topic endpoint to verify functionality and edge cases.

- refactor(backend): migrate from requests to httpx for async support in RestEndpointInvoker

* Replaced requests library with httpx to enable asynchronous HTTP requests.
* Removed request handlers dictionary and implemented a single async request method.
* Updated error handling to use httpx exceptions.
* Adjusted tests to mock httpx responses and ensure compatibility with async invocations.

- feat(adaptive-testing): enhance output generation with concurrent endpoint invocations

* Introduced asyncio support to invoke endpoints concurrently, allowing up to 50 requests at a time.
* Refactored the output generation logic to improve performance and error handling during asynchronous calls.
* Updated the processing of test outputs to ensure efficient handling of results and errors.

- feat(telemetry): implement caching for worker availability checks

* Added a module-level cache to store the availability of Celery workers, reducing the need for repeated ~3s ping calls.
* Implemented a TTL mechanism for the cache to optimize performance during endpoint invocations.
* Enhanced the worker availability check method to utilize the cache effectively, improving response times.

- feat(dependencies): update package dependencies in uv.lock and pyproject.toml

* Added new packages: aiohttp-security, aiohttp-session, joblib, and updated numpy and scikit-learn versions.
* Enhanced dependency management for improved functionality and compatibility across the project.
* Removed redundant dependencies from adaptive-testing group in pyproject.toml.

- sdfsdf

- feat(adaptive-testing): add metric selection functionality in AdaptiveTestingDetail component

* Introduced new state management for metrics, including loading state and selected metric.
* Implemented useEffect to load metrics on component mount, enhancing user experience with a metric selector.
* Updated the UI to include an Autocomplete component for metric selection alongside the existing endpoint selection.
* Improved layout for better organization of input fields for endpoint and metric selection.

- fix(backend): use per-task db sessions in generate_outputs_for_tests

The function was sharing a single SQLAlchemy session across concurrent
asyncio tasks, which is unsafe. Each task now gets its own session via
get_db_with_tenant_variables(), and all ORM writes happen sequentially
on the main request session afterward. Semaphore lowered from 50 to 10
to stay within connection pool limits.

- refactor(frontend): clean up code formatting in adaptive testing components

* Removed unnecessary line breaks and adjusted formatting for better readability in AdaptiveTestingPage, AdaptiveTestingDetailPage, AdaptiveTestingDetail, AdaptiveTestingGrid, and adaptive-testing-client.
* Ensured consistent use of single-line statements where applicable to enhance code clarity.

- refactor(frontend): improve styling consistency in AdaptiveTestingDetail and TopicTreePanel components

* Integrated useTheme hook to apply theme-based styling for border radius and font sizes, enhancing visual consistency across the components.
* Updated various elements to utilize theme typography settings for better alignment with design specifications.

- feat(frontend): conditionally display Adaptive Testing navigation item in development

* Updated the navigation items to include the 'Adaptive Testing' page only in the development environment, enhancing the development experience without affecting production.

- refactor(frontend): improve code formatting in AdaptiveTestingDetail component

* Adjusted formatting of the DeleteIcon component for better readability and consistency in the AdaptiveTestingDetail file.

- refactor(tests): update endpoint tests to use httpx.AsyncClient

* Replaced mocking of the requests library with httpx.AsyncClient in endpoint tests to align with the actual implementation.
* Enhanced test cases to properly mock asynchronous behavior and responses, ensuring accurate testing of endpoint invocations.
* Improved readability and structure of test code for better maintainability.

- fix(tests): reset worker cache in telemetry enrichment service tests

* Cleared module-level cache for worker availability checks in multiple test cases to ensure accurate mock behavior.
* Updated tests to reset the cache state before each worker availability check, preventing interference from previous tests.

- chore(workflows): rename backend test job for clarity

* Updated the job name in the backend test workflow from "🧪 Backend Tests (Local-Style)" to "Backend tests" for improved clarity and consistency.

- chore(license): add MIT License and attribution for adaptive-testing module

* Included the MIT License text in a new LICENSE file for the adaptive-testing module.
* Updated NOTICE file to reflect the addition of the adaptive-testing library and its licensing.
* Added module-level comments in **init**.py to acknowledge the source and licensing of the adaptive-testing library.

---

Co-authored-by: Claude Opus 4.5 <noreply@anthropic.com>

## [0.6.4] - 2026-02-12

### Added

- **Split-View Playground and Test Creation:** Added a split-view chat panel in the playground and a drawer for creating tests directly from conversations, pre-filled with LLM-extracted fields for both single-turn and multi-turn tests. (#1321)
- **Test Output Reuse and Re-scoring:** Introduced the ability to re-score test runs using stored outputs, without re-executing the tests. Added a "Scoring Target" dropdown to execution drawers, allowing users to choose between fresh outputs and reusing existing ones. (#1311)
- **Test Set File Import:** Implemented a file import feature for test sets, supporting CSV, JSON, JSONL, and Excel formats with column mapping and LLM-based remapping. (#1319)
- **Custom Test Run Names:** Added an optional name field to test run creation flows. (#1318)
- **User-Configurable Embedding Models:** Enabled user-configurable embedding models with a new settings page, API endpoints, and SDK support. (#1297)
- **Server-Side Filtering for Test Sets Grid:** Added server-side filtering to the test sets grid, allowing users to filter by name, type, creator, and tags.
- **Native Authentication System:** Replaced Auth0 with a native authentication system, including email/password, Google OAuth, GitHub OAuth, magic link, and email verification. (#1283)
- **Change Detection to Editable Components:** Added change detection to various editable components in the frontend, such as ContactInformationForm, OrganizationDetailsForm, BehaviorDrawer, ProjectDrawer, TestExecutableField, and metric edit sections. (#1235)
- **Playwright E2E Smoke Tests:** Added Playwright E2E smoke tests covering auth setup, page-load baseline, sidebar navigation, and page-specific assertions. (#1299)

### Changed

- **WebSocket Connections:** Optimized WebSocket connections to be page-specific, reducing unnecessary connections on pages that don't use real-time features.
- **Test Connection in Edit Mode:** Enabled test connection functionality in edit mode using stored model credentials. (#1315)
- **Multi-Turn Test Configuration:** Allowed users to pass goal, instructions, restrictions, and scenario as top-level fields on Test, with automatic test_configuration building.
- **Authentication Flow:** Unified magic link as a sign-in and sign-up flow, automatically creating user accounts for unregistered emails.
- **Default Generation Model:** Changed the default generation model from vertex_ai/gemini-2.0-flash to rhesis/default. (#1279)
- **Refresh Token Rotation:** Implemented access/refresh token rotation for improved security. (#1283)
- **Docker Images:** Migrated Docker images from Docker Hub to mirror.gcr.io. (#1275)

### Fixed

- **Newline-Separated Steps in Synthesizer Instructions:** Enforced newline-separated steps in synthesizer instructions for multi-turn tests.
- **Copy Button on Assistant Messages:** Restored the copy-to-clipboard button on assistant message bubbles.
- **Test Set Type in File Import:** Ensured the correct test set type is passed through the file import flow.
- **Mapping UI Flicker:** Eliminated mapping UI flicker on auto-advance during file import.
- **Session Ownership and Thread Safety:** Added session ownership verification, thread safety, and limits to file import sessions.
- **Abort Control and A11y in Import Dialog:** Added AbortController, memoization, and a11y improvements to the file import dialog.
- **Error Messages:** Improved error messages for model configuration and worker availability issues. (#1279)
- **Model Connection Testing:** Implemented actual model connection testing with real validation. (#1279)
- **ESLint and TypeScript Errors:** Resolved all ESLint and TypeScript errors blocking CI. (#1298)
- **React/no-array-index-key Violations:** Resolved all react/no-array-index-key violations. (#1298)
- **Auth Security:** Hardened auth security across backend and frontend, including fixing open redirect vulnerabilities and improving email verification safety. (#1283)
- **Auth Migration:** Fixed auth migration issues, making it idempotent and comprehensive. (#1283)
- **Polyphemus BetterTransformer Optimization:** Enabled BetterTransformer optimization and upgraded to CUDA base image. (#1279)
- **Validation Warnings:** Cleared validation warnings when models are no longer defaults. (#1279)

### Removed

- **Auth0 Dependency:** Removed Auth0 as a dependency. (#1283)
- **Embedding Dimensions from User Settings:** Removed user-configurable embedding dimensions. (#1297)

### Security

- **Hardened Auth Security:** Addressed several security vulnerabilities in the authentication system, including open redirect, enumeration safety, and token handling. (#1283)

## [0.6.3] - 2026-02-05

### Added

- **Playground:** Added a new interactive playground for testing endpoints with real-time WebSocket communication. This includes a new `/playground` page under the Testing section, a chat interface with message handling, and integration with TraceDrawer for viewing endpoint response traces.
- **Jira Ticket Creation:** Implemented Jira ticket creation directly from tasks via MCP integration. Users can select a Jira project and create tickets with automatic field mapping.
- **WebSocket Infrastructure:** Implemented foundational WebSocket support for real-time communication between backend and frontend with comprehensive security measures.
- **Trace Visualization:** Added a graph view for trace visualization, allowing users to switch between Tree View, Sequence View, and Graph View tabs to visualize span hierarchies.
- **Agent Tracing:** Added framework-agnostic agent tracing support with `ai.agent.invoke` and `ai.agent.handoff` span types, including agent input/output capture and handoff detection.
- **Markdown Rendering:** Added markdown rendering to playground chat bubbles for assistant messages.
- **Playground Button:** Added a "Playground" button to the endpoint detail page, navigating to the playground with the endpoint pre-selected.
- **Copy Button:** Added a copy button to playground message bubbles for easy copying of chat messages.
- **LM Format Enforcer:** Added lm-format-enforcer as a new provider.
- **Creation Dates:** Display creation dates for tests and test sets in the UI.
- **./rh dev Command:** Added a `./rh dev` command for local development setup, including starting Postgres and Redis, generating `.env` files, and running database migrations.

### Changed

- **SDK Timeout:** Increased SDK function timeout from 30s to 120s (configurable via `SDK_FUNCTION_TIMEOUT` env var).
- **SDK Connector Ping:** Increased SDK connector ping interval/timeout defaults (60s/30s) with `RHESIS_PING_INTERVAL` and `RHESIS_PING_TIMEOUT` env vars.
- **Conversation Tracking:** Standardized `session_id` as the canonical name for conversation tracking.
- **WebSocket Retry:** Enhanced WebSocket retry mechanism for robustness, including increased max reconnect attempts, a max reconnect delay cap, and a manual reconnect method.
- **Trace Detail View:** Adjusted trace detail view split to 70:30, giving more space to the trace visualization.
- **MCP Provider Names:** Simplified MCP provider names in the selection dialog.
- **Jira Space Nomenclature:** Changed nomenclature from "Jira projects" to "Jira spaces".
- **Trace Visualization:** Renamed Markov View to Graph View for clarity and removed probability labels from edges.
- **Agent Icon:** Replaced agent icon with a brain icon for `ai.agent.invoke` spans.
- **Local Development Commands:** Reorganized commands under the `rh dev` subcommand for better clarity.

### Fixed

- **WebSocket Ping Timeout:** Fixed synchronous functions blocking the event loop, preventing WebSocket ping timeouts.
- **Trace ID Propagation:** Fixed trace ID propagation from SDK to frontend for trace linking.
- **Connector Test Isolation:** Resolved connector test isolation issues.
- **Endpoint Change Reset:** Fixed resetting the entire conversation state when the endpoint changes in the playground.
- **Redis URL Configuration:** Fixed Redis URL configuration to check `BROKER_URL` first for consistency.
- **Duplicate Breadcrumb Routes:** Fixed duplicate breadcrumb routes.
- **Chart Tooltip Visibility:** Fixed chart tooltip text visibility in dark mode.
- **Header Logo Navigation:** Fixed header logo navigation causing reload and redirect.
- **Dark Mode Flash:** Prevented dark mode flash on page load.
- **Test Set Type:** Fixed test set type default selection and validation display.
- **Client Method:** Added client method to create-ticket-from-task service.
- **Span Name Validation:** Updated span name validation test for agent domain.
- **Created Column:** Kept Created column next to Type in test and test-set tables.

### Removed

- **Trace Details Cost Display:** Removed cost display from trace details (will be re-added in a future release).

## [0.6.2] - 2026-01-29

### Added

- Implemented 3-level metrics hierarchy for test execution. Added Test Run Metrics section to ExecuteTestSetDrawer with metric source selection dropdown (behavior, test set, execution-time). Includes RerunTestRunDrawer component for re-running tests with options, scope filtering in SelectMetricsDialog, and MetricsSource display in test detail view. (#1206)
- Added Garak import UI for test sets with GarakImportDialog component for selecting and importing probes, 'Import from Garak' button in TestSetsGrid, sync button for garak-sourced test sets, and garak backend icon on metric cards. Features progress indicators, visual feedback, and probe-level selection within modules. (#1190)
- Added context and expected response fields to test run detail view. Context array displays as bullet points with "No context provided" fallback, and expected response shows in the Overview tab. (#1201)
- Split Atlassian MCP provider into separate Jira and Confluence providers with dedicated credential fields for URL, username/email, and API token. Values now stored in credentials only for proper edit mode persistence. (#1197)
- Added MCP GitHub repository scope configuration with repository scope display in tool cards and import dialog. Added URL import tab (Direct Link) for importing MCP resources from URLs with provider-agnostic support. (#1148)
- Added MCP observability support with dynamic agent selection based on RhesisClient availability. (#1102)

### Fixed

- Fixed tags not showing up without refresh on source page. (#1173)
- Fixed object responses handling in trial drawer. (#1156)
- Fixed endpoint connection type being changeable during edit mode - now properly prevented. (#1158)

### Removed

- Removed Documents feature from UI in favor of source-based architecture. (#1169)

## [0.6.1] - 2026-01-20

### Fixed

- **Endpoints:** Resolved an issue where JSON data in the Endpoint Detail editor was being double-stringified, preventing correct saving and display.

### Style

- **Endpoints:** Improved code formatting and readability in the EndpointDetail component.

## [0.6.0] - 2026-01-15

### Added

- Added comprehensive telemetry traces UI with filtering and visualization capabilities. (#1088)
- Added GitHub MCP provider. (#1078)

### Changed

- Improved MCP connection stability and reliability. (#1089)
- Enhanced SDK tracing with asynchronous support, smart serialization, and improved I/O display. (#1111)
- Integrated test execution into the organization onboarding process. (#1074)
- Improved frontend consistency across various sections. (#1074)

## [0.5.4] - 2025-12-18

### Added

- Added a new "Polyphemus" provider with schema support, enabling integration with Polyphemus data sources.

### Changed

- Updated documentation with comprehensive guides and improved SDK metrics documentation.

### Fixed

- Updated `next` dependency from 16.0.7 to 16.0.10.
- Updated `nodemailer` dependency from 6.10.1 to 7.0.11.

## [0.5.3] - 2025-12-11

### Added

- Added endpoint test functionality for connection testing.
- Added multi-turn test support in manual test writer.

### Changed

- Enhanced trial drawer with multi-turn support and UX improvements.
- Improved MCP usability with various UX enhancements.
- Improved tag styling and added loading state in test run modals.

### Fixed

- Fixed filter by tag functionality.
- Fixed MCP authentication errors and improved related UX.
- Fixed cursor focus loss in title and description fields.
- Fixed display of users instead of organizations in creator chart.
- Fixed issue where task/test assignee could not be unassigned.

## [0.5.2] - 2025-12-08

### Added

- Added support for tags to test runs, allowing for better organization and filtering.
- Added categories and threshold operator support for metrics, providing more granular control and analysis.
- Added a Test Connection Tool to simplify connection troubleshooting.

### Fixed

- Fixed a security vulnerability by updating React and Next.js to patch CVE-2025-55182.
- Fixed an issue where navigation context was not properly preserved during certain tasks.

## [0.5.1] - 2025-12-04

### Added

- Modernized dashboard with MUI X charts and activity timeline.
- Added grid state persistence to localStorage.
- Added support for OpenRouter provider.
- Improved MCP import and tool selector dialogs.

### Changed

- Reduced toolbar height for a more compact header.
- Updated Dockerfile to reference `eslint.config.mjs` instead of `.eslintrc.json`.
- Backend execution RPC fixes and UI improvements.

### Fixed

- Prevented external links from appearing in breadcrumbs.
- Fixed metric creation to support both SDK and frontend approaches with proper field handling.

### Dependencies

- Bumped `next-auth` dependency.

## [0.5.0] - 2025-11-27

### Added

- Implemented client-side search filter for test results.
- Added a new behaviors page with refactored metrics UI.
- Implemented multi-turn conversation preview in the test generation flow.
- Added support for Tool Source Type.
- Implemented Tool Configuration Frontend.
- Added bidirectional SDK connector with intelligent auto-mapping.
- Added in-place test execution without worker infrastructure.
- Added basic multi-turn test generation support.
- Implemented an interactive onboarding tour system.
- Added models list for providers.
- Added an account button.

### Changed

- Redesigned the test results page with improved filters and UX.
- Redesigned the knowledge detail page for consistency with the design system.
- Reorganized navigation with sections and external links.
- Improved behavior-metrics relation UI.
- Upgraded to Next.js 16 and MUI v7.

### Fixed

- Fixed tag wrapping and placeholder text in grids.
- Fixed issues in the Test Generation Stepper.
- Resolved button disable logic and step completion issues in onboarding.
- Corrected section name in source selector message.
- Fixed permission issues in docs and frontend docker images.
- Aligned Test Config Frontend with Backend API.
- Resolved test failures and improved schema design.
- Fixed Generate Test Config Endpoint.
- Fixed telemetry deployment issues.
- Updated Dockerfile to include 'local' environment in build and start conditions.

### Removed

- Removed the logout button in local environment.
- Removed `type-check` and linter from the frontend build process.
- Removed `ncdu` dependency.

## [0.4.3] - 2025-11-17

### Fixed

- Fixed a bug that caused the frontend Docker image to fail during local deployment.
- Fixed a file ownership issue (chown bug) that could prevent the application from running correctly.

## [0.4.2] - 2025-11-13

### Added

- Added single-step MCP import workflow.
- Added MCP integration for Notion import in the knowledge page.
- Added tags and comments columns to sources grid and source detail page.
- Added Test Set Type field to test sets, displayed in frontend views.
- Added metric scope functionality for single-turn and multi-turn metrics.
- Added local development setup with Docker Compose and auto-login feature.
- Added RocketLaunchIcon to LandingPage for Local Mode display.
- Added test type column and multi-turn goal display in test set detail grid.
- Added multi-turn test configuration UI, integrated into the test detail page.

### Changed

- Simplified MCP import workflow to a single-step process.
- Improved MCP import UX and fixed theme violations.
- Improved multi-turn test UI components and metrics display.
- Enhanced metrics tab with visual indicators and collapsible sections.
- Replaced metric scope multi-select with intuitive selectable chips.
- Updated tests grid to show test type and multi-turn goal.
- Improved test type visual distinction in tests grid.
- Replaced slider with number input for max turns in multi-turn test configuration.
- Updated test title to show goal for multi-turn tests.
- Improved grid layout in knowledge page with flexible columns.

### Fixed

- Improved multi-turn test metrics serialization and frontend display.
- Corrected multi-turn test review display and conflict detection.
- Resolved TypeScript errors in TestsTableView and other frontend components.
- Fixed various PR checker issues and added comprehensive tests.
- Fixed display of metrics for multi-turn tests in test run detail view.
- Resolved ESLint warnings in metrics frontend components.
- Prevented button overlap on single-line fields (Max. Turns).
- Fixed TypeScript linting errors in TestDetailData.
- Fixed theme styles and spacing consistency.
- Allowed detail page access for both rhesis and custom metrics.

### Removed

- Removed Microsoft and Apple login options.
- Removed redundant Score Type label in metric detail view and new metric creation page.
- Removed local development configuration files.
- Removed placeholder goal banner.

## [0.4.1] - 2025-10-30

### Added

- Added support for additional file formats (.pptx, .xlsx, .html, .htm, .zip) for source uploads.
- Added drag-and-drop file upload component for sources.
- Added source indicators to test and test set grids.
- Added context sources to test generation and display in test samples.
- Added project selector to test input screen.
- Added a warning notification when content extraction fails during source upload.
- Added Error status display for test results without metrics.
- Added a re-run button to the test run detail page.
- Added reviews tab to split view and conflict indicators for test runs.
- Added creator information to test sets.
- Added quick search with OData filtering to the test runs grid.
- Added partial status and execution error indicators to test runs.
- Implemented global 404 and 410 error handling with restore functionality.
- Integrated OpenTelemetry for enhanced monitoring.
- Added local deployment models and providers.

### Changed

- Replaced 'Document' terminology with 'Source' throughout the frontend.
- Replaced ContextPreview with a document icon in grids.
- Improved source display in test and test-set pages.
- Updated test generation to use sources instead of documents.
- Updated Rhesis model naming and descriptions.
- Improved AI-based test generation with improved UI and backend support.
- Enhanced hashing mechanism in telemetry for user and organization IDs.
- Updated schemas and initial data for metrics.
- Improved BaseDataGrid quick filter using an uncontrolled input.
- Updated Rhesis Managed badge styling.
- Improved test template usage and flows between screens.
- Made default model indicators more subtle.
- Implemented full editing functionality for knowledge sources.
- Updated test generation to allow an optional test set name parameter.

### Fixed

- Fixed missing ContentCopyIcon import.
- Fixed exhaustive-deps warnings in the `useComments` hook.
- Fixed source name display in confirmation and interface screens for test generation.
- Fixed upload endpoint URL for sources.
- Fixed API key requirement for local deployments.
- Fixed merge conflicts.
- Fixed hardcoded styles.
- Fixed misleading loading state in source preview.
- Fixed 'Name' to 'Title' in source detail.
- Fixed TypeScript error with Chip icon prop in TestRunsGrid.
- Fixed incorrect status color for completed test runs.
- Fixed display of execution time for failed and partial test runs.
- Fixed error breadcrumbs to be reactive to navigation changes.
- Fixed issue where the execute button was enabled when a test set had 0 tests.
- Fixed issue where test results chart had a hardcoded limit of 5 runs.
- Fixed issue where organisation name overlapped.

### Removed

- Removed unused documents section and DescriptionIcon import.
- Removed unused documents state and import.
- Removed undefined documents reference from TestConfigurationConfirmation.
- Removed remaining document references from test generation components.
- Removed scenarios from test templates config and test generation flow.
- Removed the 'rhesis' provider from the user-selectable provider list.
- Removed automatic content extraction during source upload.
- Removed telemetry settings and related components.
- Removed binary score type from new metrics page and metrics detail page.
- Removed import button from manual test writer.

## [0.4.0] - 2025-10-16

### Added

- Implemented Knowledge section with source upload functionality, OData filtering for sources grid, and enhanced source preview with content block design and uploader information display.
- Added comments column to SourcesGrid.
- Implemented user settings API client and interfaces.
- Added conditional endpoint field for self-hosted model providers.
- Added test connection button to model dialog.
- Added friendly error messages with expandable technical details.
- Added validation for website, logo URL, email, and phone fields in organization settings.
- Implemented leave organization feature.
- Added editable test set title functionality.
- Added advanced filtering for test results in test runs.
- Added review management methods to API client.
- Added 'Conflicting Review' filter option.
- Added Tasks & Comments tab to test detail panel.
- Implemented reusable StatusChip component for consistent status display.

### Changed

- Standardized delete button styling across the entire platform.
- Standardized date format to DD/MM/YYYY across knowledge components.
- Moved Knowledge section to appear after Projects in the navigation.
- Improved Knowledge components to match the test-sets pattern.
- Refactored integrations menu to display Models first.
- Renamed "llm-providers" to "models" for consistency.
- Redesigned test runs detail page with a modern dashboard interface.
- Refactored test detail charts with dynamic data and enhanced UI.
- Improved API key field UX and reduced card width.
- Updated model cards to match metrics styling and apply consistent width constraints.
- Applied consistent width constraints to Applications and Tools pages.
- Constrained models page width to match metrics styling.
- Extended DeleteModal with word confirmation, optional top border, bold text support, and simplified DangerZone.
- Improved status card layout and typography in TestRunHeader.
- Improved comparison view layout and real-time comment updates.
- Simplified Review column in table view to a dual-icon system.

### Fixed

- Resolved blank file downloads in the knowledge section.
- Resolved code formatting issues.
- Resolved infinite loop in SourcesGrid component.
- Updated params type for Next.js 15 compatibility.
- Resolved hydration mismatch in date formatting.
- Resolved infinite loading in tasks section.
- Resolved flickering data grid on test runs page.
- Resolved duplicate import ESLint error in TokensGrid.
- Improved token deletion confirmation message.
- Aligned token empty state with theme.
- Resolved user deletion 500 error.
- Prevented automatic headers from being stored in request_headers.
- Prevented button text flicker when closing dialog and in edit mode.
- Properly cleared default model settings when toggling off.
- Improved disabled button visibility and added connection test requirement alerts.
- Corrected machine icon to show original automated result.
- Resolved TypeScript errors and linting issues.
- Fixed hardcoded style violations and replaced them with theme values.
- Fixed Prettier formatting issues.
- Fixed hardcoded styles in DangerZone.
- Fixed hardcoded style values to comply with theme standards.
- Fixed hardcoded font sizes with theme values.
- Fixed hardcoded values with theme tokens.
- Fixed theme borderRadius instead of hard-coded values.
- Fixed Prettier formatting in TasksSection.
- Fixed escape apostrophes in DomainSettingsForm text.
- Fixed: always send endpoint field in test connection request.
- Fixed: preserve natural error messages from all providers in connection test.
- Fixed: fetch all provider types by adding limit parameter.
- Fixed: remove server-side console.logs causing hydration errors.
- Fixed: actually pass additionalMetadata when creating tasks.
- Fixed: correct entity type for tasks created from test results.
- Fixed: improve token deletion confirmation message.

### Removed

- Removed all comment functionality from sources.
- Removed back and copy buttons from source preview header.
- Removed formatted/raw toggle from source preview.
- Removed white container wrapper from source preview.
- Removed header section from Knowledge page.
- Removed file type icons from SourcesGrid title column.
- Removed editor settings from user settings.
- Removed subscription section from organization settings.
- Removed domain settings from organization settings page.
- Removed redundant View Details action.
- Removed redundant test count display.
- Removed step prefix from evaluation steps edit fields.

## [0.3.0] - 2025-10-02

### Added

- Implemented comprehensive frontend testing infrastructure with Jest and React Testing Library.
- Added pre-commit hooks for code formatting and linting.
- Added comments and tasks count columns to entity DataGrids.
- Implemented server-side search for test set selection.
- Added editable task title with validation.
- **Complete rebranding**: Introduced new Rhesis AI logos, color palette, and visual design system.
- Added a demo route with Auth0 login_hint integration.
- Added theme-based circular border radius support.
- Added complete versioning information for backend and frontend.

### Changed

- **Complete application rebranding**: Updated entire application with new Rhesis AI theme, fonts, color palette, and brand elements.
- Redesigned the demo page with a professional UI and brand elements.
- Enhanced task detail page with navigation button and improved UI consistency.
- Standardized avatar sizes and consolidated task details UI.
- Improved metric card chips and UI behavior.
- Improved test results interface clarity.
- Truncated project description after 250 characters in ProjectCard.
- Optimized chart space utilization and fixed alignment issues.
- Improved visual consistency across onboarding components.
- Updated logo to increased platypus variant with dark mode support.
- Reduced default sidebar width.
- Standardized font sizes and added typography variants to the theme.

### Fixed

- Resolved duplicate key error in Run Test Drawer with same project names.
- Resolved initial load issue and improved error handling for tasks.
- Resolved task details page error.
- Resolved TypeScript error in TestSetSelectionDialog useRef initialization.
- Improved error handling and prevented flickering in task components.
- Resolved GitHub Actions testing issues.
- Resolved React 19 compatibility issues in GitHub Actions.
- Fixed hardcoded styles and validation issues across various components.
- Fixed inconsistencies in chip colors and elevation issues.
- Prevented charts from reloading on tab focus.
- Standardized layout consistency and axis visibility across all chart components.
- Improved endpoints detail page design consistency.
- Corrected elevation prop usage to use numeric values.

### Removed

- Removed redundant Final_Summary.md and testing documentation files.
- Removed workflow section from metrics, test-sets, and test-runs pages.
- Removed reports navigation item.

## [0.2.4] - 2025-09-18

### Added

- Added "Source Documents" section to individual Test Detail page, displaying associated documents.
- Added "Source Documents" section to Test Set Details page, displaying associated documents.
- Added document, name, and description fields to the Test Set interface.
- Added `test_metadata` field to the `TestBase` interface.
- Added a send button to the comment text box.

### Changed

- Updated project title and description to update reactively upon editing, without requiring a page reload.
- Updated breadcrumb and title in the test header to display content instead of UUID.
- Improved test coverage.

### Fixed

- Ensured compatibility between comment and token frontend interfaces and the backend.
- Fixed test stepper return behavior.

## [0.2.3] - 2025-09-04

### Added

- Added dynamic charts for test run details.
- Added comments feature for collaboration on tests, test sets, and test runs.
- Added error boundary for improved application stability.
- Added loading spinners to metrics creation and deletion processes.

### Changed

- Improved performance of the test run stats endpoint.
- Optimized API client interfaces and behavior client methods.
- Refactored metrics functionality into separate components for better maintainability.
- Improved environment variable handling for local development and deployment flexibility.
- Updated Dockerfile for enhanced build process and environment configuration.

### Fixed

- Fixed tooltip visibility issues across different themes.
- Fixed display issues with tooltips for test runs.
- Fixed TypeScript warnings.
- Fixed flickering issue in the test run datagrid.
- Eliminated unnecessary re-renders in the metrics detail page.
- Fixed inconsistencies and re-renders during metric editing.
- Resolved issues with multiple API calls during metric editing.
- Fixed display of metrics confirmation page during creation.
- Fixed issue where metrics not associated with behaviors were not displayed.
- Fixed macOS IPv6 localhost connection issues.

## [0.2.2] - 2025-08-22

### Added

- Added document upload step with automatic metadata generation.
- Added support for Central European, Nordic, and Eastern European characters in BaseTag validation.
- Updated frontend supported file extensions to match SDK.

### Changed

- Refactored docker-compose and environment configuration.
- Improved migration and start up scripts for docker backend.
- Adjusted frontend Dockerfile to production mode.
- Updated Complete Setup button behavior after successful onboarding.
- Changed 'Generated Name' and 'Generated Description' to just 'Name' and 'Description' in the frontend.
- Updated supported file extensions for document upload.

### Fixed

- Fixed issue where projects were not automatically refreshing after new project creation.
- Fixed issue where long project names were truncated.
- Fixed various issues in the document generation configuration flow, including:
  - State persistence.
  - Inconsistent button behavior.
  - Test coverage labels.
  - Button label and description.
  - Field label naming.
  - Behaviors and topics display in the final step.
  - File size validation.
  - Next button validation on the first step.
- Fixed `handleNext` double step increment bug.
- Improved document metadata extraction using a structured prompt format.
- Fixed document upload state updates.

### Removed

- Removed projects-legacy and unnecessary navigation items.
- Removed unnecessary refresh button.
- Removed unsupported file extensions (.url, .youtube).

## [0.2.1] - 2025-08-08

### Added

- Introduced Test Results functionality, allowing users to view and analyze test outcomes.
- Added interfaces for handling test results statistics.

### Fixed

- Resolved an issue causing infinite loading for test sets.

### Changed

- Updated contributing guides to reflect new PR creation and update features.

## [0.2.0] - 2025-07-25

### Added

- Display of frontend version information in the application.
- Environment variables are now accessible to the client-side application.
- Functionality to add users outside of the onboarding flow.
- Introduced a team invitation stepper with email uniqueness check, proper email validation, rate limiting (10 invites/hour), and max team size (10).
- Download button added to the test run view.
- Added snack bar notification to test set execution.

### Changed

- Improved team invitation security and validation.
- Enhanced error handling and duplicate detection in team invitation.
- Improved BasePieChart legend position.
- Updated dependencies: `form-data` from 4.0.1 to 4.0.4.
- Adjusted total prompts to total tests throughout the frontend.
- Improved generation of test cases.
- Improved and refactored task orchestration.
- Made run time display more user-friendly.
- Improved contrast in dark mode.

### Fixed

- Prevented email addresses from being used as first names during onboarding.
- Fixed duplicate identifier issues in BaseDataGrid.
- Fixed contrast issues in dark mode.
- Ensured server logout upon session expiration.
- Cleared validation errors for the frontend.
- Hardened application logout and synchronized backend/frontend logout.
- Fixed chips display for test sets and other entities.
- Test set execution via test run list is now functional again.
- Fixed session length issues in the backend/frontend.
- Fixed test set pagination.
- Fixed missing expected response in reliability prompts.
- Fixed the display of behaviors in the context of test runs.
- Fixed execution time display for progress test runs.
- Fixed test run data grid header.
- Fixed total tests display for test runs.
- Fixed endpoint creation notification.
- Fixed new endpoint page.
- Fixed race condition when displaying endpoint.
- Fixed adjusting total_tests display in runs data grid.
- Fixed not showing notification when adding tests to testset.
- Fixed application and endpoint selection not showing values.
- Fixed the testset selection field name as key instead of id as key issue.
- Fixed completion timestamp and endpoint fields.
- Fixed issue with styling in LLM provider overview (grid).
- Replaced empty columns in test run grid.
- Fixed unescaped strings.
- Fixed Windows-type authentication.

## [0.1.0] - 2025-05-15

### Added

- Initial release of the frontend application
- Next.js 15 with App Router implementation
- Material UI v6 component library integration
- Authentication system with NextAuth.js
- Protected routes and middleware
- Dashboard with test management interface
- Projects management screens
- Test sets and test cases visualization
- Test runs monitoring
- API client integration with backend services
- Dark/light theme support
- Responsive design for desktop and mobile
- User onboarding flow
- Organization management

### Note

- This component is part of the repository-wide v0.1.0 release
- After this initial release, the frontend will follow its own versioning lifecycle with frontend-vX.Y.Z tags

[Unreleased]: https://github.com/rhesis-ai/rhesis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/v0.1.0

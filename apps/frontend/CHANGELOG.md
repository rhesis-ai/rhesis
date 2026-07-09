# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-07-09

### Added

- **Role-Based Access Control (RBAC) UI (Enterprise Edition):**
  - Introduced a new **Roles** tab in Organization Settings to view built-in roles and manage custom roles.
  - Added a **Role Editor Drawer** featuring a graded permission model across four resource areas and four capability levels (None, View, Edit, Manage).
  - Added **

## [0.9.1] - 2026-06-25

Changed / Redesigned\*_:
_ Redesigned Insights page as a behavior-centric pass rate view with behavior columns, scoped metrics/topics, and drill-down capabilities.
_ Redesigned `/tools` page to use a provider card grid and aligned the connection drawer with Figma designs.
_ Unified date and time formatting across the platform to use browser timezone with `

## [0.9.0] - 2026-06-11

### Added

- **Endpoint Creation Wizard:** Introduced a new interactive wizard for creating endpoints, including a test-and-map user interface.
- **Behavior Tags:** Added support for tagging behaviors, enabling better organization and grouping.
- **Project-Level Isolation:** Implemented project-level isolation, ambient scope, and security hardening for the project switcher.
- **Support Drawer:** A new support drawer has been added to the sidebar for easy access to help and resources.
- **Multi-step Model Provider Flow:** Converted model provider selection and connection flows into a multi-step drawer for an improved user experience.

### Changed

- **UI Redesign (major):** Comprehensive redesign aligned with the Figma design system, touching every major page — Experiments, Test Runs, Explorer, Playground, Project, Task, Tokens, and Organization settings — plus the run/invite/support drawers and entity grids on metric & behavior detail pages.
- Project switcher now persists the default project selection across sessions.
- Organization menu reorganized for improved navigation.
- Metrics and Models navigation items are now visible to all users.
- Test creation flow refactored and manual writer UI aligned with the new design.

### Fixed

- **Traces Page Issues:** Resolved incorrect empty state, race condition during project-scoped data fetches, incorrect project scope in TraceDrawer API calls, and hidden traces grid.
- **Endpoints Grid Hotfix:** Addressed a hotfix issue related to the endpoints grid.
- **Search Contrast:** Improved contrast for search elements for better readability.
- **Project Switcher Hotfix:** Applied a hotfix for the project switcher.
- **Sticky Action Bar:** Fixed the sticky behavior of the Action Bar.
- **Onboarding Project Fetch:** Prevented unnecessary project fetches during the onboarding process.
- **Sidebar Display:** Corrected sidebar alignment for project names and removed email from user information.
- **Backend URL Resolution:** Ensured `BACKEND_URL` is correctly resolved at runtime for `/api/auth-config`.
- **Knowledge Drawer:** Prevented the MCP tool selection from inadvertently closing the drawer.
- **Endpoint Mapping Tab:** Reverted a change that passed an auth token in the mapping tab test request, addressing a potential regression.

## [0.8.0] - 2026-05-21

### Added

- **Parameter Management and Experiments:** Introduced project-scoped parameter schemas, versioned experiments, and label routing (now Environments). Includes a project-level parameter schema editor, experiment detail page with typed forms, version history diffs, and latest-results aggregations.
- **Experiment Selection for Test Runs:** Added an experiment selector to execution drawers, allowing users to pin parameter values when running tests.
- **Server-Side Experiment Management:** Implemented server-side filters, search, and inline editing for experiments.
- **Experiment Chip in Test Run Comparison View:** Added a link to the experiment page in the Baseline Run and Current Run cards of the comparison view.
- **Multi-Version Experiment Selection:** Enabled selecting multiple versions from the same experiment in the picker dialog for test runs.
- **Parameters Tab on Experiment Detail:** Added a Parameters tab to the experiment detail page, reusing the ProjectParameters component.
- **Interactive RHESIS_API_KEY Setup:** Added interactive detection and prompting for RHESIS_API_KEY on `rh start` if missing or a placeholder.
- **File Handling Support:** Added support for image source type and extraction, allowing the system to handle image and document files as test inputs.
- **Test Explorer User Guide:** Added documentation for the Test Explorer feature, including an overview, workflow, and scenarios.
- **Architect Task Progress Events:** Added WebSocket events for live updates from background workers to the Architect chat session.
- **Architect Task Progress UI:** Added a task progress trail to the Architect chat UI, providing live updates on background tasks.
- **Adversarial Test Generation Notebook:** Added a Polyphemus adversarial test generation notebook example.

### Changed

- **Terminology Update:** Renamed "Labels" to "Environments" for parameter routing.
- **Parameter Injection:** Unified parameter injection via `{{ params.* }}` in request mappings, replacing the legacy `@endpoint(parameters=...)` approach.
- **Project UI Patterns:** Standardized project and experiment UI patterns.
- **Execution Drawers:** Unified multiple execution drawers into a single RunDrawer component.
- **Experiment Version IDs:** Replaced content-hash version identifiers with sequential numbering (v1, v2, v3).
- **Test Clusters Panel:** Improved the Test Clusters panel hover UX and unified tests list and clusters in a tabbed panel.
- **Architect Agent Plan Tracking:** Enhanced Architect agent plan tracking with progress summaries and improved mapping logic.
- **Architect Agent Entity Resolution:** Implemented a typo-tolerant entity resolution ladder for the Architect agent.
- **SSO Feature Gating:** Moved SSO into EE and added community boundary guard.
- **API Base URL Resolution:** Resolved the frontend API base URL at runtime instead of build time.
- **Default Embedding Model:** Set `rhesis/rhesis-embedding` as the default embedding model.
- **Quick Start Mode:** Resolved QUICK_START at runtime instead of build time.
- **Architect Task Progress Trail:** Unified exploration progress trail into streaming bubble.
- **Architect Needs Confirmation:** Derived architect needs_confirmation from per-turn block state.

### Fixed

- **Security Vulnerabilities:** Fixed security vulnerabilities across all projects by bumping dependencies.
- **MUI Component Warnings:** Resolved MUI component warnings and select value issues.
- **Turbopack CPU Bug:** Used webpack for the dev server to avoid a turbopack CPU bug.
- **Embedding Graph Poll Cancellation:** Restored embedding graph poll cancellation.
- **Vertex AI Credentials:** Passed Vertex AI credentials in-memory instead of using temporary files.
- **CNPG Service Account Name:** Fixed the CNPG service account name in Kubernetes deployments.
- **OOM Issues:** Fixed OOM issues in the backend and permission issues in the frontend.
- **DNS Resolution:** Resolved DNS issues inside the Kubernetes cluster.
- **OIDC Metadata Resolution:** Resolved OIDC metadata outside the JWKS cache lock.
- **Token Exchange Flow:** Wired end-to-end token-exchange flow.
- **Rate Limiting:** Added post-parse limiter for body-keyed throttles.
- **JTI Replay Protection:** Namespaced single-use JTI by issuer.
- **Security Hardening:** Applied security review hardening for API clients.
- **Refresh Token Security:** Required active user and uniform 401 on `/auth/refresh`.
- **Auth Client Uniqueness:** Scoped auth_client uniqueness to live rows.
- **Feature Gate Enforcement:** Enforced feature gate at runtime and required epoch on azp JWTs.
- **PermissionError on Logs Dir:** Resolved PermissionError on logs directory during e2e startup.
- **Event Loop Errors:** Always used background thread in `run_sync` to prevent event loop errors.
- **Streaming Output Bleed:** Prevented streaming output bleed across Architect sessions.
- **OTEL Exporter Batch Chunking:** Added batch chunking to OTEL exporter.
- **Architect Agent UX:** Architect agent UX improvements and exploration progress trail.
- **Architect Needs Confirmation:** Architect needs_confirmation derived from per-turn block state.
- **Ghost Empty Bubbles:** Prevented ghost empty bubbles after multi-iteration resumed turn.
- **Missing Mappings:** Required mappings in plan, prohibited mid-execution save_plan.
- **Rate Limit IP Address:** Corrected `get_real_ip` index for X-Forwarded-For.
- **EE Tests:** Ran EE tests correctly and fixed `/features` token auth.
- **ORM Data Migrations:** Used raw SQL in ORM-based migrations to avoid column mismatch.
- **TLS Pinning:** Fixed TLS pinning, redirect context, and slug dedup.
- **File Handling:** Addressed architectural layering and eliminated duplicate logic in file handling.
- **API Base URL:** Resolved frontend API base URL at runtime instead of build time.

### Removed

- **Legacy Parameter Approach:** Removed the legacy `@endpoint(parameters=...)` approach for parameter injection.
- **Dead ExplorerClient Methods:** Removed dead ExplorerClient methods (validateTree, getTreeStats, path-based getTopic) and TreeValidation / TreeStats types.
- **TaskProgressList Component:** Removed TaskProgressList component and taskProgressToToolStreams adapter.

## [0.7.1] - 2026-05-07

### Added

- Added live task progress updates to the Architect chat session, displayed inline within the message bubble.
- Added a typo-tolerant entity resolution ladder to the Architect agent, improving its ability to understand misspelled entity names.
- Added Explorer feature for managing and interacting with test sets.
- Added adaptive testing tree endpoints and schemas.

### Changed

- Unified the exploration progress trail into the streaming bubble, removing the separate task progress bubble.
- Improved Architect agent UX with exploration progress trail and other enhancements.
- Collapsed and hid the Architect task progress trail after completion, displaying a "Done." marker.
- Enhanced glossary definitions and examples for Trace, Connector, and Playground terms.
- Renamed adaptive testing to explorer and updated related endpoints.

### Fixed

- Fixed streaming output bleed across Architect sessions.
- Fixed an issue where the Accept/Change confirmation UI was incorrectly displayed.
- Fixed an issue where the plan widget would jump inconsistently during execution.
- Fixed an issue where ghost empty bubbles would appear after multi-iteration resumed turns.
- Fixed a validation error in E2E tests related to EndpointEnvironment.
- Fixed an issue where whitespace-only token names could be submitted.
- Only dismiss plan widget when plan is complete.
- Restore Done. marker and show Executing label during task.
- Prevent submission of whitespace-only token names.

### Removed

- Removed the TaskProgressList component and related types, as task progress is now integrated into the streaming bubble.
- Removed Next public Auth0 and app URL env configuration.

## [0.7.0] - 2026-04-23

### Added

- Rhesis Architect: introduced an AI agent for intelligent test suite design and execution.
- Adaptive Testing: enabled navigation to adaptive testing features, including embeddings and diversity-aware suggestions.
- Model Selection: added support for flexible model selection and execution models.

### Changed

- Disabled the `@mention` user interface.
- Updated the login page badge label.
- Temporarily disabled the default embedding model selection.

### Fixed

- Resolved frontend connectivity issues in Docker environments by standardizing default endpoints to `host.docker.internal`.

## [0.6.12] - 2026-04-09

### Added

- Added a built-in "echo" use case to the chatbot that returns the user's input verbatim without invoking the LLM or consuming any rate-limit quota.
- Added a POST `/test_runs/{id}/cancel` endpoint to cancel test runs.
- Added a "Cancel Test Run(s)" button to the frontend that appears when one or more queued/in-progress runs are selected.
- Added mid-flight cancellation via an asyncio watchdog that polls Celery's in-process revoke set.
- Added a mop-up pass to retry transient failures after the main batch execution in test runs.
- Added support for "Turn Config" / "turn_config" / "turns" / "num_turns" columns in file imports to configure multi-turn tests.
- Added batch accept functionality for adaptive test suggestions in the frontend.
- Added a segmented progress bar for the adaptive testing suggestions pipeline in the frontend.
- Added streaming capabilities for suggestion generation and evaluation in adaptive testing, allowing for real-time updates.
- Added export functionality for adaptive test sets to create regular test sets.
- Added user feedback functionality for suggestion generation in adaptive testing.
- Added per-metric evaluation details to the backend.
- Added score metrics tooltip to the frontend.
- Added adaptive test set settings read/update flows for managing default endpoint and metric assignments through dedicated API routes.
- Added a "Tests without topic" option in AdaptiveTestingDetail to filter and display tests that do not have an associated topic.

### Changed

- Replaced chord fan-out with an async batch execution engine for test runs, improving concurrency and resource utilization.
- Switched the Celery worker from prefork to threads pool to eliminate fork() and related native library crashes.
- Invokers, endpoint service, and metrics evaluators now have async support.
- Updated BaseLLM.warmup() and VertexAILLM.warmup() docstrings to remove fork-safety framing.
- Improved telemetry ingestion error logging with stage tracking, exc_info tracebacks, and worker availability logging.
- Adaptive testing now uses adaptive test set settings as the default source for endpoint and metric selection.
- Increased default per-test timeout from 300s to 1800s (30 min).
- Updated the default sort order in the test retrieval function for adaptive testing to descending.

### Fixed

- Fixed SIGTRAP/SIGKILL during concurrent Vertex AI tests by passing credentials directly.
- Fixed stuck Progress status on TestRun by catching Celery task_failure and task_revoked signals.
- Fixed bugs in the batch engine and invoker layer, including misplaced docstrings, thread-safety races, and incorrect error handling.
- Fixed negative duration on failed test runs in the frontend.
- Fixed raw HTML parsing in markdown to prevent React error #137.
- Fixed telemetry tasks to bind to the Redis Celery app.
- Fixed file import issues, including skipping blank leading rows, handling multi-sheet workbooks, and skipping empty rows.
- Fixed adaptive testing tests for evaluate and settings client.
- Fixed auth manager mock target in tests.
- Fixed RPC close bug and eliminated per-invocation object construction for performance improvements.

### Removed

- Removed the option to overwrite existing outputs in adaptive testing, defaulting to true for output generation.

## [0.6.11] - 2026-03-26

### Added

- Added trace metrics tab displaying per-metric evaluation results with status indicators, scores, and explanations.
- Added trace reviews tab with the ability to submit human review overrides for traces, individual turns, and specific metrics.
- Added trace review drawer for creating reviews with target type selection, pass/fail toggles, and comment validation.
- Added project-level trace metrics configuration page with bulk metric selection and removal via a data grid.
- Added evaluation status filter (Passed/Failed/Pending) to the traces list page.
- Added dedicated trace detail page at `/traces/[identifier]`.
- Added `hideFooter` prop to `BaseDataGrid` component.
- Added Trace scope option to metric forms and filters.
- Added `conversation_id` to `TraceQueryParams` interface.
- Added error boundary around trace drawer tab content for improved resilience.

### Changed

- Consolidated review target label maps into a shared `TRACE_REVIEW_TARGET_LABELS` constant.
- Tightened `MetricScopeValue` type by removing the `| string` escape hatch.
- Replaced hardcoded `color: 'white'` and `rgba()` values in TraceFilters with MUI theme tokens.
- Memoized span attribute categorization in SpanDetailsPanel using `useMemo`.
- Removed unused state and callbacks from TracesClientWrapper.
- Aligned trace metrics display style with test-run metrics layout.

### Fixed

- Fixed `useMemo` called conditionally after early return in SpanDetailsPanel, violating rules of hooks.
- Fixed TypeScript error: cast metric ID to UUID template literal for `getMetric` calls.
- Fixed status filter functionality and removed unused status column from traces table.
- Fixed span detail tab indices using string values for stability.
- Fixed missing trace metrics extraction in telemetry service.

## [0.6.10] - 2026-03-23

### Added

- Redesigned login and register pages with a white-dominant design, floating auth card, decorative SVG background, top nav bar, and hero copy.
- Added the ability to delete adaptive testing test sets.
- Added an "Attachments" column to the tests grid, displaying the number of file attachments for each test.
- Added overwrite functionality for test generation and evaluation in adaptive testing.
- Added bulk delete functionality for tests in the AdaptiveTestingDetail component.
- Added evaluate endpoint and UI for adaptive testing.
- Added suggestion generation and evaluation endpoints for adaptive testing.
- Added file attachments to conversation message bubbles in test runs.
- Added NIST-aligned password hardening with zxcvbn strength scoring, context-specific word blocking, and HaveIBeenPwned breach checks.
- Added E2E test coverage for playground, metrics CRUD, test run result actions, and onboarding.
- Added E2E test coverage across 16 new spec files.

### Changed

- Updated password policy to align with NIST guidelines, requiring a minimum password length of 12 characters and a minimum strength score.
- Improved error handling for rate-limit and registration errors.
- Updated vulnerable dependencies to address security alerts.
- Enhanced adaptive testing output generation and evaluation with overwrite options.
- Improved metric evaluation and scope filtering in adaptive testing.
- Centralized enum constants and fixed migration syntax.
- Refactored adaptive testing code for improved readability and consistency.
- Consolidated API calls and removed redundant fetches to optimize backend performance.
- Replaced complex SQLAlchemy queries with PostgreSQL views for improved performance.
- Reverted to the original single-row layout for the SearchAndFilterBar.

### Fixed

- Fixed a bug where advanced filters showed metrics from all linked behaviors instead of those evaluated in the current test run.
- Fixed a bug where selecting a metric in advanced filters produced 0 results due to a name mismatch.
- Fixed test run stats display, ensuring accurate reporting even with partial API responses.
- Fixed "no runs yet" flicker on the test-runs page.
- Fixed search functionality on the test run detail page.
- Fixed Garak dynamic import dialog auto-closing on completion.
- Fixed an issue where calculating the pass rate for a test run relied on `first()` returning the correct `Status` record.
- Fixed counts including soft-deleted records.
- Fixed MCP auth to use the system default model and corrected credential testing for HTTP providers.
- Fixed Notion integration link to the internal integrations page.
- Fixed tests grid random reordering with stable secondary sort.
- Fixed onboarding StaleDataError caused by RLS session variable loss after db.commit().
- Fixed broken filter layout on the metrics overview page.
- Fixed an issue where the TraceDrawer opened with the wrong turn selected in test runs.
- Fixed a Jinja2 rendering issue where `file_contents` was rendered as the string "None" instead of Python None.
- Fixed a potential TypeError in TestRunCharts data generators by adding defensive null checks.
- Fixed a potential ValueError in `get_test_run_metrics` by guarding the organization_id UUID conversion.
- Fixed a potential issue where the debounced sync effect in OnboardingContext could schedule a redundant DB write.
- Fixed a potential issue where the initialSelectedTestId deep-link page was overridden on mount.

### Removed

- Removed assignee and owner fields from the test run configuration.

## [0.6.9] - 2026-03-12

### Added

- Added multi-target review annotations for test runs (turns, metrics, test results).
- Added categorized @mention support in review comments for metrics and conversation turns.
- Added resizable split panel to the test list / detail view.
- Added configurable anchor prop to BaseDrawer.
- Added pagination, search, and filters to the projects list.
- Added per-turn metadata, context, and tool_calls to conversation evaluation.
- Added comprehensive E2E test coverage for all overview and detail pages.
- Added dynamic probe support to garak import.

### Changed

- Updated TestRunHeader pass rate, TestsList, and overview tab to reflect review overrides.
- Improved metric selection dialog with auto-focus, full metric fetching, and scope filtering.
- Renamed "Penelope" documentation section to "Conversation Simulation".
- Upgraded garak to v0.14 with dynamic probe generation and code quality fixes.
- Updated docker base image to python 3.12.
- Improved metric selection dialog and centralized metric scopes.

### Fixed

- Fixed MuiDrawer theme override scoping to prevent ToggleButton color overrides.
- Fixed issue where turns without criteria didn't show pass/fail labels.
- Fixed TypeScript errors in PlaygroundChat and client-auth tests.
- Fixed SelectMetricsDialog loading state reliability.
- Fixed TypeScript type errors in new test files.
- Fixed disambiguation of duplicate project names and metric scope filter.
- Fixed emoji linter violation for penelope icon.
- Fixed test set execute button being disabled for manually created test sets.
- Fixed 21 Dependabot security vulnerabilities.
- Fixed test set metadata after bulk test creation and use actual count for execute button.
- Fixed CI failures in e2e and a11y tests.
- Fixed remaining e2e test failures.
- Fixed endpoints heading and projects-crud click-through tests.
- Fixed op.execute() call and frontend prettier formatting.
- Fixed no-op migration.
- Fixed omission of Goal line in \_build_prompt when no dedicated goal exists.
- Fixed preservation of mappings when LLM correction omits them.
- Fixed use of double-brace syntax in placeholder examples.
- Fixed use of tool.value in generate_tool_description f-strings.
- Fixed use of sx theme callback in renderMentionText.
- Fixed guard against None in \_compute_review_state existing_ts.
- Fixed restoration of body styles on unmount during resize drag.
- Fixed deep-copy input dict in MessageHistoryManager.add_message.
- Fixed null from ProjectsQueryParams.$filter type.
- Fixed index-based React key for context list items.

### Removed

- Removed threatening attribution alert from review modal.
- Removed unused auth0-lock dependency.

### Refactor

- Renamed goal metric to `goal_achievement` to align with the SDK.
- Extracted review service layer and addressed DRY violations.
- Replaced magic strings with TestSetType constants.
- Replaced tool message keys with named constants.
- Addressed code review findings in garak services.

## [0.6.8] - 2026-03-05

### Added

- Added frontend E2E CRUD tests, unit tests, Firefox coverage, and accessibility tests.
- Added Playwright CRUD interaction specs for tokens, test sets, projects, and endpoints.
- Added TestSetsPage and TokensPage page objects for E2E tests.
- Added Firefox browser project to playwright.config.ts.
- Added unit tests for TokensClient, ProjectsClient, TestSetsClient.
- Installed jest-axe and added accessibility tests for common components.
- Added multi-file attachment support for tests, traces, and playground, including file upload/download/delete endpoints and UI components.
- Added file format filters and trace file linking for endpoint invocations.
- Added file upload support to the `/chat` endpoint.
- Added file attachment UI to Playground Chat.
- Added file download to FileAttachmentList and MessageBubble.
- Added file attachment support to multi-turn tests in Penelope.
- Added file attachment support to SDK entities.
- Added metadata and context as collapsible sections in test run detail view.
- Added "Go to Test" button linking to test detail page in test run detail view.
- Added trace drawer and file sections to test run detail view.
- Added required field validation to metric creation form.
- Added LiteLLM Proxy, Azure AI, and Azure OpenAI provider support.
- Added hook and component tests, expanding MSW infrastructure.
- Added API client integration tests for BaseApiClient, TestsClient, TestRunsClient, and EndpointsClient.
- Added page-level integration tests for grid components.
- Added detail-page integration tests.

### Changed

- Replaced test type magic strings with constants.
- Renamed file data field from `content_base64` to `data` for consistency.
- Moved file attachment button inside text input in Playground Chat.
- Enhanced test run detail view with metadata, context, and JSON content display.
- Updated Node.js version to 24 in CI configurations and Dockerfiles.
- Moved e2e tests to `tests/e2e/` and dropped coverage threshold.
- Updated `@icons-pack/react-simple-icons` to v13.12.0.
- Moved file position query to CRUD layer.

### Fixed

- Used correct TestResultStatus values in accessibility tests.
- Fixed CI failures in E2E and accessibility tests.
- Fixed remaining E2E test failures related to onboarding checklist, DataGrid aria-label matching, and endpoint navigation.
- Fixed test-sets E2E tests targeting MUI Select trigger.
- Created `.auth` directory before writing `storageState` to prevent auth setup failures.
- Included `test_set_type_id` when creating test sets from manual writer.
- Fixed manual test writer test set association and navigation.
- Resolved focus loss in metric evaluation steps TextFields.
- Rebased file migration on litellm provider migration.
- Used theme borderRadius and passed missing sessionToken.
- Added default for `user_id` in TestRunCreate schema.
- Resolved TypeScript errors in model providers and test creation.
- Addressed PR review feedback for file filters and upload positions.
- Handled optional `prompt_id` in test components.
- Handled null `polyphemus_access` in user settings.
- Patched `MAX_MESSAGE_SIZE` in websocket tests to prevent hang.
- Added required `score_type` fields to metric test data factories.
- Handled non-string content in MarkdownContent.
- Prevented input focus loss from inline component definitions.
- Resolved EndpointFormAutoConfigure test timeouts.
- Lowered branch coverage threshold to match CI measurement.
- Resolved TypeScript type errors in test fixtures.
- Handled invalid test run ID gracefully with `notFound()`.
- Used main content locator in POM `waitForContent` instead of grid.
- Updated `auth.setup.ts` `storageState` path to `tests/e2e/.auth/`.
- Simplified conditional checks for optional API key in models.
- Corrected formatting in ConnectionDialog for azure_ai provider.
- Handled lazy-load failures in mixin relationship properties.
- Used CRUD layer for test set attribute updates.
- Removed `[DEBUG]` prefix from API error logs.

### Removed

- Removed outdated `.nvmrc` file specifying Node.js version 20.19.5.

## [0.6.7] - 2026-03-02

### Added

- Added explicit `min_turns` parameter for early stop control in conversational evaluations.
- Added `add_tests()` and `remove_tests()` methods to the SDK `TestSet` for bulk test association.
- Added `min_turns` and `max_turns` support to test configuration import/export and synthesizer.
- Added client-side pagination to the metrics grid.

### Changed

- Replaced the single "max turns" input with a turn configuration range slider on the test detail page and dual number inputs in the manual test writer, allowing configuration of both `min_turns` and `max_turns`.
- Renamed `max_iterations` to `max_turns` throughout the codebase to better reflect the semantics of conversation turns.
- Updated the conversational judge to count turns as user-assistant pairs instead of individual messages.
- Improved early stopping behavior in conversational evaluations, preventing early termination before reaching 80% of `max_turns`.
- The `push()` method in the SDK now supports both creating (POST) and updating (PUT) metrics.
- Updated metrics page to paginate metrics fetch to show all backend type tabs.

### Fixed

- Fixed focus loss and stale save button in the metric editor.
- Fixed metric update overwriting with null values in the backend.
- Fixed an issue where conversational metrics were not receiving the `conversation_history` parameter during evaluation.
- Fixed an issue where the metrics page was not displaying all backend type tabs due to a fetch limit.
- Fixed an issue where the max-turns stop reason detection was using a stale "max iterations" string.

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

### Added

- Introduced AI-powered auto-configuration for endpoint mappings, streamlining setup and integration.
- Added the capability to evaluate three-tier metrics during live multi-turn executions.
- Integrated a default Rhesis embedding model, simplifying initial configuration for new projects.
- Implemented options to duplicate existing endpoints, behaviors, and metrics.
- Introduced adaptive testing capabilities to improve the robustness and relevance of test runs.

### Changed

- Standardized terminology across the application for improved clarity and consistency.

### Fixed

- Resolved an issue with test run metric filtering that prevented accurate data display.
- Addressed several bugs affecting the creation of new endpoints.

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

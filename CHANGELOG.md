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

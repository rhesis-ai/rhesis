# Backend Changelog

All notable changes to the backend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
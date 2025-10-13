# Backend Changelog

All notable changes to the backend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2025-10-13

### Added
- Implemented soft delete functionality for users, tests, and other data models, including recycle bin management endpoints for restoring deleted items.
- Added support for test reviews, including API endpoints for review manipulation, a `test_reviews` column to test results, and derived properties `matches_review` and `last_review` on test results.
- Implemented encryption for sensitive data in the Model and Token tables, including endpoint authentication fields.
- Added a hash-based token lookup mechanism for encrypted tokens.
- Added a "leave organization" feature for users.
- Added GDPR user anonymization function.
- Added individual test statistics endpoint.

### Changed
- Updated CRUD utilities and QueryBuilder to support soft deletion.
- Enhanced test configuration generation and schema.
- Refactored test statistics into a dedicated stats module.
- Re-inviting users who left organizations is now supported.

### Fixed
- Resolved issues with soft delete filtering in raw queries.
- Fixed a 500 error on user removal by implementing soft delete.
- Corrected organization filtering and token count for tokens.
- Addressed worker-based generation issues.
- Explicitly set the Gemini model in test generation.
- Enabled tags, tasks, and comments for test results.

### Removed
- Removed legacy comment lines in `database.py`.
- Removed SDK configuration and added a model parameter for test generation.
- Removed frontend content related to test reviews, moving documentation to the backend.


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
# Backend Changelog

All notable changes to the backend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
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

# Polyphemus Changelog

All notable changes to the polyphemus component will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.6] - 2026-02-26

### Added
- Implemented rate limiting for the Polyphemus service to prevent abuse and ensure stability.
- Added access control and delegation tokens to the Polyphemus service for enhanced security and authentication. This includes:
    - Service delegation tokens for Polyphemus authentication.
    - Access control system with request/grant workflow.
    - Database migrations for Polyphemus models and access control.
    - Polyphemus-aware model resolution in user_model_utils.
    - Email notification template for access requests.
- Added delegation token validation to the Polyphemus service, enabling backend-to-Polyphemus authentication via JWT tokens alongside the existing API key authentication.
- Added frontend support for Polyphemus model access including:
    - Access request modal and API route.
    - Model card UI states for Polyphemus access control.
    - Polyphemus provider icon and logo.
    - User settings interface with is_verified field.
- Deployed vLLM to Vertex AI, enabling access to advanced language models.
- Added a `DEFAULT_POLYPHEMUS_URL` environment variable to deployment configurations, allowing the backend to reach the Polyphemus adversarial model service per environment.

### Changed
- Replaced `python-jose` with `PyJWT` for token validation to address security vulnerabilities.
- Cached GCP credentials and shared the HTTP client in the Polyphemus service for improved performance.
- Updated model name mapping with configurable variables for vLLM on Vertex AI.
- Updated dependencies to address multiple security vulnerabilities, including:
    - `cryptography` to >= 46.0.5
    - `pillow` to >= 12.1.1
    - `fastmcp` to >= 1.23.0
    - `langgraph-checkpoint` to >= 3.0.0
    - `marshmallow` to >= 3.26.2
    - `virtualenv` to >= 20.36.1
    - `mammoth` to >= 1.11.0
    - `langchain-core` to >= 1.2.11
- Reduced the default timeout for Vertex AI requests from 600s to 120s.

### Fixed
- Fixed multiple security dependency vulnerabilities across all packages.
- Fixed an issue where the endpoint name filtering was incorrect for vLLM on Vertex AI.
- Fixed token and comment test failures.
- Fixed an issue where the `FROM_EMAIL` environment variable was not used for access request recipients.
- Fixed an issue where the `is_verified` field was missing from the UserSettings schema.
- Fixed an issue where `test_set_type` was missing during test set creation.
- Fixed broad exception swallowing in `check_quota` function.
- Fixed a bug where the `--skip-existing` CLI flag was not working as expected in `deploy.py`.
- Fixed an issue where the frontend TestSetBulkCreate interface did not match the backend schema.
- Fixed an issue where `from_json`, `from_jsonl`, and `from_csv` methods were not correctly inferring the `test_set_type`.
- Fixed an issue where the GCP service account email secret name was incorrect in the CI workflow.
- Fixed a permission issue related to GCP credentials.
- Fixed an issue where the deployment failed when the endpoint was empty.
- Fixed an issue where "default" was not accepted as a model alias.

### Removed
- Removed `python-jose` as a dependency from the worker and Polyphemus components.
- Removed unused `is_for_training` parameter from the `check_quota` function.
- Removed dead code related to extracting the prompt from messages.


## [0.2.5] - 2026-02-12

### Fixed
- **Security:** Resolved multiple Python security vulnerabilities by upgrading the following packages: `cryptography`, `nbconvert`, `langsmith`, `protobuf`, `python-multipart`, `fastmcp`, `urllib3`, `aiohttp`, `FastAPI`, `starlette`, and `langchain-core`.
- **Performance:** Enabled BetterTransformer optimization in Polyphemus, resulting in a 1.5-2x inference speedup. This was achieved by fixing the BetterTransformer implementation to use the correct optimum API and upgrading to a CUDA base image for better GPU stability.
- **Error Handling:** Improved error messages for model configuration and worker availability. Users now receive clear, actionable error messages when model API keys are missing or invalid, model providers are unsupported, model names are incorrect, or Celery workers are unavailable.
- **Docker:** Improved Docker build resilience with apt-get retry logic and fixed incorrect `mirror.gcr.io` image paths for Postgres and Redis. Also, prevented `rh delete` from removing manually created containers by adding Docker Compose project name isolation.
- **Model Validation:** Fixed issues related to model validation, including showing API error details in the test generation flow, treating LLM error dicts as failures, and including actual error details in API error responses. Validation warnings are now cleared when models are no longer defaults.

### Changed
- **Default Model:** Changed the default generation model from `vertex_ai/gemini-2.0-flash` to `rhesis/default` to use the Rhesis system model by default, allowing the platform to work out of the box without requiring external API keys for basic functionality.
- **Model Description:** Updated the description of all Rhesis Default models to "Default Rhesis-hosted model." for consistency across all organizations.
- **PyTorch Dependency:** Made PyTorch an optional dependency via `cpu` and `gpu` extras. The default Dockerfiles now use the `--extra cpu` option.

### Added
- **Model Connection Testing:** Implemented actual model connection testing using ModelConnectionService to validate model configurations and return detailed error messages.
- **Frontend Validation:** Added validation for all default models (not just Rhesis) and improved error message handling to show actual validation errors in the frontend.
- **Health Check:** Added a health check endpoint to the Polyphemus Dockerfile.
- **GPU Computation Test:** Added a GPU computation test and enhanced GPU debug logging.


## [0.2.4] - 2026-01-15

### Added
- Added `bind` parameter to the endpoint decorator, enabling dependency injection. This allows for more flexible and testable endpoint implementations. (#1112)

### Changed
- Refactored the underlying storage mechanism to utilize a Bucket Model. This change improves data organization and scalability. (#1067)


## [0.2.3] - 2025-12-18

### Added
- Added support for specifying custom HTTP headers when fetching data sources. This allows for authentication and other advanced use cases.

### Changed
- Improved error handling when a data source is unavailable. Polyphemus now provides more informative error messages.
- Refactored the data processing pipeline for improved performance and scalability.

### Fixed
- Fixed an issue where Polyphemus would occasionally fail to parse certain date formats.
- Resolved a bug that caused incorrect data aggregation when dealing with timezones.


## [0.2.2] - 2025-12-11

### Fixed
- **Rate Limiter:** Resolved an issue where the rate limiter was executing before authentication, potentially allowing unauthorized requests to consume rate limit resources. (#1031)


## [0.2.1] - 2025-12-04

### Added
- Added an `is_verified` field to the User model. This field indicates whether a user's email address has been verified.


## [0.2.0] - 2025-11-27

### Added
- Implemented authentication for Polyphemus.
- Added support for deploying Polyphemus in Google Cloud Run.
- Introduced cost heuristic for Polyphemus benchmarking.
- Implemented context retention and refusal metrics.
- Added random sampling and dataset conversion functionalities.
- Introduced summaries and reports generation.
- Implemented initial metrics using LLM-as-a-Judge.

### Changed
- Refactored the entire Polyphemus benchmarking framework for improved readability and maintainability.
- Rewrote benchmarking framework to integrate SDK modules and improved model handling.
- Improved prompting strategies.
- Transitioned to using classes for custom metrics.
- Restructured the project to facilitate deployment to Google Cloud.

### Fixed
- Resolved issues in evaluation summary calculations.
- Fixed model registration problems with testers.
- Corrected Hugging Face model loading behavior.
- Fixed bugs in result curation.
- Improved judge model memory management.
- Addressed pathing issues.
- Resolved issues in overall score calculation from metrics.
- Optimized file access.

### Removed
- Removed redundant path joining.


## [0.1.0] - 2025-01-08

### Added
- Initial release of the Polyphemus LLM inference and benchmarking service
- FastAPI-based REST API for text generation with Dolphin 3.0 Llama 3.1 8B model
- Support for streaming and non-streaming text generation endpoints
- Modular benchmarking suite for model evaluation and selection
- Abstract model interface with HuggingFace and mock model implementations
- Test framework with test sets and scoring logic
- Basic test sets and examples (e.g., `mock_test_set.json`)
- OWASP-based security test sets for model harmfulness and integrity evaluation
- Pre-built model configurations for various LLM models (Hermes3, Dolphin3, Vicuna, Kimi K2)
- Health check endpoints with GPU status monitoring
- AMD GPU support documentation and setup guide for ROCm (`AMD.md`)
- Docker containerization with Cloud Build integration for deployment

### Changed
- Updated structure: moved and renamed files to match SDK conventions
- Added `pyproject.toml`; removed `requirements.txt`

### Note
- After this initial release, Polyphemus will follow its own versioning lifecycle with polyphemus-vX.Y.Z tags

[Unreleased]: https://github.com/rhesis-ai/rhesis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/v0.1.0

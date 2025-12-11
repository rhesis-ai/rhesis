# Polyphemus Changelog

All notable changes to the polyphemus component will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

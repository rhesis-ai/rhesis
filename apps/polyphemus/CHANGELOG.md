# Polyphemus Changelog

All notable changes to the polyphemus component will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-06-11

### Changed

- build(docker): pin uv to 0.11.19 in service images (#1882)

Avoid :latest drift and align chatbot/telemetry-processor with COPY --from mirror.gcr.io/astral/uv.
- fix(docker): pull uv from mirror.gcr.io instead of ghcr (#1879)

Avoid GHCR auth failures during local builds by using the GCR mirror
of Docker Hub's official astral/uv image.



## [0.3.0] - 2026-05-21

### Changed

- chore(deps): fix security vulnerabilities across all projects (#1791)

Bump direct and transitive dependencies to resolve 56 Dependabot
alerts (12 HIGH, 44 MEDIUM) across Python and npm ecosystems.
- 1727 differing results using polyphemus between sdk and platform (#1773)

* refactor(polyphemus): harden adversarial primer to ban harmless outputs

* fix(polyphemus): inject primer before schema instructions, not after

* feature(polyphemus): "harmful" mode for synthesizer

* fix(polyphemus): restored missing system prompt case

---------

Co-authored-by: Alexey <alexey@rhesis.ai>
- feat(polyphemus): inject adversarial system primer on every request (#1752)

Co-authored-by: Alexey <alexey@rhesis.ai>
- chore(deps): patch Dependabot security advisories across the monorepo (#1747)

* chore(deps): patch Dependabot security advisories across the monorepo

Resolves ~145 of 156 open Dependabot alerts by bumping direct
dependencies, adding/updating uv constraint-dependencies, and adding npm
overrides for vulnerable transitive packages. Lockfiles regenerated
across all 9 Python projects (sdk, packages/rhesis, apps/backend,
apps/chatbot, apps/polyphemus, apps/telemetry-processor, penelope,
examples/telemetry, agents/research-assistant) and both npm projects
(apps/frontend, docs/src). npm audit reports 0 vulnerabilities in both
JS projects.

Direct dependency bumps:
  - python-multipart >= 0.0.27 (backend)
  - cryptography >= 46.0.7 (sdk, backend)
  - langchain-core >= 1.2.28 (sdk, penelope, research-assistant, examples)
  - notebook >= 7.5.6 (penelope)
  - transformers >= 5.0.0rc3 (sdk huggingface extra)
  - next ^16.2.3 + nodemailer ^8.0.5 (frontend)
  - next ^15.5.15 (docs)

Transitive constraints / npm overrides bumped or added:
  - gitpython, mako, mistune, jupyterlab, jupyter-server, nbconvert,
    lxml, langchain-{openai,text-splitters}, langsmith, litellm, pytest
  - dompurify, lodash, lodash-es, postcss, fast-xml-parser, protobufjs,
    uuid, handlebars, picomatch, yaml, flatted, @xmldom/xmldom,
    brace-expansion

Added exclude-newer-package = false for jupyter-server, mistune, and
notebook (sdk, backend, penelope) to allow uv to pick up the May 3-4
security patches that the 1-week cutoff would otherwise filter out.

Remaining alerts (no fix applied):
  - fastmcp 3 CVEs: blocked by mcp-atlassian pinning fastmcp<2.15.0
  - lupa, ragas, diskcache: no upstream patch available yet

* chore(sdk): tighten transformers spec to >=5.0.0 (no pre-releases)

Address review feedback: `transformers>=5.0.0rc3` permits pre-releases
because the specifier itself includes an rc segment. Stable 5.0.0 is
already published and the lockfile resolves to 5.5.4, so requiring
stable 5.x is the right intent.
- chore(dependencies): update package versions and add new dependencies (#1688)

- Updated `cryptography` from 46.0.5 to 46.0.7 and `pillow` from 12.1.1 to 12.2.0 in `pyproject.toml`.
- Added `aiohttp` (>=3.13.5) and `langchain-openai` (>=1.1.14) to constraint dependencies.
- Updated `python-dotenv` to 1.2.2 and `pydantic` to 2.13.0 in override dependencies across multiple projects.
- Adjusted `click` version from 8.2.1 to 8.1.8 in several projects for compatibility.
- Updated `exclude-newer` timestamps in `uv.lock` files to reflect new dependency versions.
- build(dev): remove rust from polyphemus dockerfile (#1687)
- refactor(backend): split deps into core and [all] extras (#1686)

* refactor(backend): split deps into core and [all] extras

Slim down the migrate image and decouple Polyphemus from the heavy
ML stack by separating core deps from optional ones.

- Core: web stack (fastapi/uvicorn/slowapi), workers (celery/redis),
  OpenTelemetry, FastAPI utils, and migration prerequisites.
- [all] extra: rhesis-sdk, rhesis-penelope, garak, mirascope,
  huggingface_hub, google-genai, gcsfs, sendgrid, mcp-atlassian.
- Inline garak metric definitions in the c2d3e4f5a6b7 migration so
  alembic upgrade head no longer imports rhesis-sdk.
- Move ScoreType / ThresholdOperator into a local metric_types module
  so models and schemas don't pull rhesis-sdk into the import graph.
- Add build-core and migrate stages to apps/backend/Dockerfile;
  build-backend syncs with --extra all --extra cpu.
- CI now builds and pushes ${IMAGE_NAME}-migrate alongside the
  regular backend image; the migrate Cloud Run job uses the slim one.
- Drop the torch uninstall hack from apps/polyphemus/Dockerfile and
  declare slowapi explicitly in apps/polyphemus/pyproject.toml.

* refactor(backend): drop unused sdk/penelope from polyphemus image

Now that polyphemus depends on rhesis-backend core only (no [all]
extra), rhesis-sdk and rhesis-penelope no longer appear in
apps/polyphemus/uv.lock. Stop shipping their source trees in the
container and remove the corresponding dead [tool.uv.sources] /
override-dependencies entries.

- Builder: copy only sdk/pyproject.toml (still needed by
  packages/rhesis [tool.hatch.version] for version reading at wheel
  build time); drop full sdk/ and penelope/ COPYs and the seds that
  patched their now-removed source paths.
- Runtime: drop /app/sdk, /app/penelope, and /app/packages/rhesis
  copies. Only /app/.venv (with the built rhesis wheel), /app/src
  (polyphemus), and /app/apps/backend (editable rhesis-backend) are
  needed at runtime.
- pyproject: remove dead [tool.uv.sources.rhesis-sdk],
  [tool.uv.sources.rhesis-penelope], and the datasets override that
  was there to reconcile garak vs rhesis-sdk (neither is in the
  polyphemus dependency tree any more).

* chore: formating

* fix(Dockerfile): update paths in pyproject.toml for uv compatibility

Revised the paths in the Dockerfile to ensure that all [tool.uv.sources] entries point to valid locations. This change addresses the need for uv to resolve paths correctly, as rhesis-sdk and rhesis-penelope are not installed in the current context. Updated the sed commands to reflect the new paths for sdk and penelope.

* chore(ci): remove disk cleanup step from polyphemus workflow

Eliminated the disk space cleanup step in the GitHub Actions workflow for the Polyphemus project. This change simplifies the workflow by removing unnecessary commands that were previously used to free up disk space on the runner.
- fix(polyphemus): log batch item failures instead of silently swallowing them (#1628)

Co-authored-by: Alexey <alexey@rhesis.ai>
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



## [0.2.9] - 2026-04-09

### Added
- Added an Attachments column to the tests grid, displaying the number of attached files.
- Implemented NIST-aligned password hardening, including zxcvbn strength scoring, context-specific word blocking, and HaveIBeenPwned breach checks. Minimum password length increased to 12 characters.
- Added the ability to set the VLLM logging level via the `VLLM_LOGGING_LEVEL` environment variable.

### Changed
- Updated password policy UI and error handling to align with the new NIST-aligned password policy.
- Improved test run advanced filters metrics by fetching only the metrics used in the current test run.
- Improved performance of test run metrics fetching by using a Postgres query to retrieve distinct metric names.
- Updated vulnerable dependencies to address Dependabot security alerts.
- Updated `langgraph` to version 1.0.10 to address an unsafe msgpack deserialization vulnerability.
- Updated `mcp-atlassian` to version 0.21.0 to address an arbitrary file write/RCE vulnerability.
- Updated `tornado` to version 6.5.5 to address a DoS vulnerability.
- Modified MCP agent to use the system default model instead of the user's configured model.

### Fixed
- Fixed a StaleDataError during onboarding caused by RLS session variable loss after `db.commit()`.
- Fixed a broken filter layout on the metrics overview page.
- Fixed an issue where tasks created from the single-turn test result drawer did not store `test_run_id` metadata.
- Fixed tests grid random reordering by adding a stable secondary sort.
- Fixed counts including soft-deleted records in Comments, Files, and Tasks.
- Fixed the Notion integration link to point to the internal integrations page.
- Fixed an issue where the MCP agent could return raw file contents or markdown-wrapped responses instead of a JSON array.

### Removed
- Removed PyTorch from the Polyphemus Docker image, reducing the image size.
- Removed Assignee and Owner fields from the Test Run Configuration.


## [0.2.8] - 2026-03-12

### Added
- Added basic test cases for the Polyphemus service, including `generate_batch` tests.
- Implemented `generate_batch` method to handle multiple requests.

### Changed
- Upgraded Dockerfile base images to Python 3.12.8-slim.
- Updated `requires-python` to `>=3.12` in `pyproject.toml`.
- Upgraded dependencies to address security vulnerabilities, including `authlib`, `google-cloud-aiplatform`, and `langgraph-checkpoint`.
- Upgraded `langgraph` to version 1.0.10 in multiple components.
- Added `[tool.uv] override-dependencies` to resolve `datasets` version conflict.
- Replaced `POLYPHEMUS_REGION` environment variable with the shared `REGION` environment variable.
- Implemented rolling model replacement for Vertex AI deployments to ensure zero-downtime updates.

### Fixed
- Fixed JSON schema format in the Vertex AI endpoint.
- Resolved dependency conflicts related to the `datasets` package.
- Addressed multiple security vulnerabilities reported by Dependabot.


## [0.2.7] - 2026-03-02

### Added
- Added support for specifying custom HTTP headers in Polyphemus requests. This allows users to authenticate with APIs that require specific header-based authentication schemes.
- Added a new `--timeout` option to the Polyphemus CLI to allow users to configure the request timeout duration.

### Changed
- Improved error handling for network connectivity issues. Polyphemus now provides more informative error messages when encountering connection errors.
- Updated the default user agent string to include the Polyphemus version number.

### Fixed
- Fixed an issue where Polyphemus would incorrectly parse URLs containing special characters.
- Resolved a bug that caused Polyphemus to crash when encountering malformed JSON responses.


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

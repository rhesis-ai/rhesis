# SDK Changelog

> **Migration Notice:** As of May 2025, this SDK has been migrated from its own repository 
> (https://github.com/rhesis-ai/rhesis-sdk) into the Rhesis main repo 
> (https://github.com/rhesis-ai/rhesis). All releases up to v0.1.8 were made in the original repository.
> While the SDK is at version 0.1.8 internally, it's included in the repository-wide v0.1.0 release tag
> for the initial release. After this, the SDK will continue with its own versioning using sdk-vX.Y.Z tags.

All notable changes to the Rhesis SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.3] - 2026-02-05

### Added
- Added a new interactive endpoint playground accessible under the "Testing" section. This allows real-time WebSocket communication for conversational endpoint testing, including chat message handling, TraceDrawer integration, and session management.
- Added JSON and JSONL import/export functionality for TestSets, enabling users to easily load and save test data.
- Added a "Playground" button to the endpoint detail page, pre-selecting the endpoint in the playground.
- Added markdown rendering to playground chat bubbles for improved readability.
- Added a copy button to playground message bubbles for easy content sharing.
- Added a graph view for trace visualization, providing an alternative to the tree view.
- Added framework-agnostic agent tracing support with new span types and attributes for multi-agent systems.
- Added CompiledGraph patching for LangGraph auto-instrumentation, simplifying callback injection.
- Added lm-format-enforcer as a new provider.

### Changed
- Increased the default SDK function timeout from 30s to 120s, configurable via the `SDK_FUNCTION_TIMEOUT` environment variable.
- Increased SDK connector ping interval/timeout defaults to 60s/30s, configurable via `RHESIS_PING_INTERVAL` and `RHESIS_PING_TIMEOUT` environment variables.
- Standardized `session_id` as the canonical name for conversation tracking, normalizing various field names.
- Enhanced the WebSocket retry mechanism with increased reconnect attempts, a maximum reconnect delay, and a manual reconnect method.
- Improved token extraction from LLM responses with support for various token sources and metadata formats.
- Refactored the LangChain integration for better modularity and maintainability.
- Adjusted the trace detail view split to 70:30, giving more space to the trace visualization.
- Replaced the agent icon with a brain icon for better visual consistency.
- Updated Gemini model example to `gemini-2.0-flash`.

### Fixed
- Fixed an issue where synchronous endpoint functions would block the event loop, causing WebSocket ping timeouts. Now, they run in a thread pool.
- Fixed Redis URL configuration to prioritize `BROKER_URL` for consistency.
- Fixed connector test isolation issues by addressing mock behavior and executor input handling.
- Fixed trace_id propagation from the SDK to the frontend for trace linking in synchronous functions.
- Fixed an issue where only the sessionId was reset when switching endpoints in the playground; now all state is cleared.
- Fixed AttributeError in HuggingFaceLLM `__del__` method.
- Fixed overwriting of passed kwargs.

### Security
- Upgraded `protobuf` to >=3.25.5 to address CVE-2026-0994 (JSON recursion depth bypass).
- Upgraded `python-multipart` to >=0.0.22 to address CVE-2026-24486 (arbitrary file write).


## [0.6.2] - 2026-01-29

### Added

- Added Model entity with provider auto-resolution. Accepts provider name string (e.g., "openai") instead of UUID, auto-resolves via type_lookups API, includes user settings management for default generation/evaluation models, and get_model_instance() for converting to BaseLLM. (#1132)
- Added Project entity with comprehensive integration tests for CRUD operations. (#1127)
- Added batch processing with generate_batch method for LiteLLM-based providers supporting system prompts, schemas, and multiple completions per prompt. (#1149)
- Added embedders framework with BaseEmbedder class, LiteLLMEmbedder, OpenAIEmbedder, GeminiEmbedder, and VertexAIEmbedder for generating single and batch embeddings. (#1149)
- Added Vertex AI support with VertexAIEmbedder and VertexAILLM classes including credential handling and configuration loading. (#1149)
- Added GarakDetectorMetric class for evaluating LLM responses using Garak detectors with threshold-based probability scoring. (#1190)
- Added ObservableMCPAgent with OpenTelemetry tracing for automatic LLM and tool invocation tracing using @observe decorators and semantic spans. (#1102)
- Added PATCH method to Methods enum in APIClient for partial resource updates. (#1165)
- Added context and expected response fields display support for test run detail view. (#1201)

### Changed

- Refactored metrics context validation to SDK. Metrics requiring context now return visible failure results with unified error messages ("<metric> metric requires context to evaluate. No context was provided.") instead of being silently skipped. Removed unused 'error' field from SDK metric results. (#1200)
- Enhanced Endpoint class with request_mapping, request_headers, response_mapping, auth_token, method, endpoint_path, and query_params fields for full programmatic configuration. Added write-only fields support to handle sensitive fields like auth_token in pull-modify-push workflows. (#1189)
- Separated API client from observability client (APIClient vs RhesisClient). RhesisClient is now optional in production, with from_environment() factory that gracefully falls back to DisabledClient when credentials are missing. (#1155)
- Added copy button to documentation code blocks and improved navigation spacing. (#1177)
- Upgraded security-related dependencies to address vulnerabilities. (#1174)
- Standardized context and ground truth requirements across DeepEval and Ragas metrics with consistent requires_context and requires_ground_truth attributes. (#1201)

### Fixed

- Fixed connector disabled variable handling. Changed RHESIS_CONNECTOR_DISABLE to RHESIS_CONNECTOR_DISABLED and updated workflow environment variables. (#1167)
- Fixed SDK entity bugs: TestRun.status now properly extracts status from nested dict, TestSet.test_set_type validator extracts type_value correctly. Added Endpoints collection class for name-based retrieval. (#1129)
- Fixed backend test cleanup transaction errors by combining all database operations into a single transaction. Added proper asyncio.CancelledError handling and RuntimeError prevention during SDK connector initialization. (#1142)
- Updated langchain-core to 1.2.5 and urllib3 to 2.6.3 to address security vulnerabilities. (#1160)
- Updated aiohttp to fix compatibility issues. (#1164)
- Fixed database connection leak with generator-based dependency cleanup in @endpoint decorator, similar to FastAPI's Depends with yield pattern. (#1102)
- Fixed resource leak on bind param initialization failure by ensuring cleanup handlers are populated in-place for partial failure cleanup. (#1102)



## [0.6.1] - 2026-01-15

### Added
- Implemented continuous slow retry mode for connector resilience. This new mode allows the SDK to automatically retry failed connector operations with increasing delays, improving stability and reliability in unstable network environments. (#1123)


## [0.6.0] - 2026-01-15

### Added
- Added `bind` parameter to the endpoint decorator for dependency injection, enabling more flexible endpoint configurations.
- Added name-based entity lookup in the SDK `pull` method, allowing for easier retrieval of entities.
- Added `project_id` field and `ConnectionType` enum to the `Endpoint` class.
- Added OpenTelemetry integration and a basic telemetry system for enhanced observability.
- Added Github MCP Provider for connecting to Github resources.
- Added Chatbot Intent Recognition functionality.

### Changed
- Enhanced SDK tracing with asynchronous support, smart serialization, and improved I/O display for better debugging and performance analysis.
- MCP connection logic has been improved for increased reliability and stability.
- MCP now supports multiple transport protocols.
- Implemented a bucket model for improved data handling.


## [0.5.2] - 2025-12-18

### Added
- Added support for categories and threshold operators for metrics.
- Introduced a new Polyphemus provider with schema support.

### Changed
- Improved generation prompts with research-backed Chain-of-Thought (CoT) and a balanced testing framework.
- Enhanced SDK test configuration and result reporting.
- Improved MCP (Managed Configuration Platform) error handling and usability.

### Fixed
- Fixed metric creation to support both SDK and frontend approaches with proper field handling.
- Hotfix for MCP compatibility issues with `npx` and `bunx`.


## [0.5.1] - 2025-12-01

### Added
- Added support for OpenRouter as a provider.
- Added Rhesis SDK examples.

### Changed
- Enhanced Penelope notebooks with configuration sections.

### Fixed
- Fixed API key issues in Penelope notebooks.


## [0.5.0] - 2025-11-27

### Added
- Added bidirectional SDK connector with intelligent auto-mapping.
- Added comprehensive multi-turn test support.
- Added support for Google Cloud integration (Polyphemus).
- Added functionality to list available models for providers.

### Changed
- Improved synthesizers for enhanced performance and functionality.
- Refactored base entity for improved code structure and maintainability.
- Updated MCP Tool Database functionality.

### Fixed
- Fixed multi-turn test generation response format.
- Fixed MCP Tool arguments.
- Ensured correct `test_type` for single and multi-turn tests.
- Resolved test failures and improved schema design.
- Fixed Ollama provider compatibility.

### Removed
- Removed `synthesizers_v2`.


## [0.4.2] - 2025-11-17

### Added
- Added support for custom HTTP headers in API requests. Users can now configure specific headers for authentication or other purposes.

### Changed
- Improved error handling for network requests. More descriptive error messages are now provided to the user.
- Updated the internal retry mechanism for failed API calls to be more robust.

### Fixed
- Fixed an issue where the SDK would incorrectly parse dates in certain locales.
- Resolved a bug that caused occasional crashes when handling large data responses.


## [0.4.1] - 2025-11-13

### Added
- Added support for Penelope Langchain integration.
- Added LangGraph metrics example.
- Added multi-turn test synthesizer functionality.
- Added scenarios feature for test case generation.
- Added cost heuristic for Polyphemus benchmarking.
- Added schema support for Hugging Face models.
- Added SDK support for metric scope and test set type.
- Added example workflow demonstrating MCPAgent usage.
- Added schemas for search and extraction results within MCPAgent.
- Added `stop_on_error` parameter to MCPAgent.
- Added Endpoint entity with invoke method for easier API interaction.
- Implemented structured output for tool calling via Pydantic schemas.
- Implemented native Rhesis conversational metrics with Goal Achievement Judge.
- Added core conversational metrics infrastructure, including Turn Relevancy and Goal Achievement.
- Added goal-achievement-specific template with excellent defaults for metrics.
- Added ConversationalJudge architecture demo.
- Added comprehensive GoalAchievementJudge test cases.
- Added optional `chatbot_role` support in conversational metrics.

### Changed
- Refactored MCPAgent to accept `Union[str, BaseLLM]` for the `model` parameter.
- Renamed `llm` parameter to `model` in MCPAgent for consistency.
- Refactored MCPAgent architecture for improved modularity and reusability.
- Consolidated agent ReAct loop into BaseMCPAgent.
- ConversationalJudge is now numeric by default.
- Upgraded DeepEval dependency to version 3.7.0.
- Output size now defaults to 2048 tokens.

### Fixed
- Resolved linting issues in various SDK components.
- Improved VertexAI provider reliability and error handling.
- Resolved Vertex AI empty OBJECT properties error in MCPAgent.
- Improved JSON parsing error handling in MCPAgent.
- Fixed Hugging Face model loading behavior.
- Fixed comprehensive code review fixes for multi-turn metrics.

### Removed
- Removed obsolete design documents.
- Removed non-conversational DeepEval metrics.
- Removed provider-specific filtering from MCPAgent executor.
- Removed application-specific schemas from MCPAgent.
- Removed redundant verbose output in MCPAgent.
- Removed old files after MCPAgent restructure.
- Removed sql alchemy dependency.


## [0.4.0] - 2025-10-30

### Added
- Added Vertex AI provider with hybrid authentication support.
- Added Cohere model support.
- Added support for both plain and OpenAI-wrapped JSON schemas in LLM providers.
- Added iteration context support to test generation.
- Added source_id tracking to tests generated from documents.
- Integrated Ragas metrics for evaluating RAG systems, including faithfulness and aspect critic metrics.
- Integrated enhanced DeepEval metrics, including a bias metric.
- Added DeepTeam model support.

### Changed
- Refactored metrics to use a new configuration-based initialization, improving validation and flexibility.
- Updated DeepEval integration to be compatible with v3.6.7 API.
- Improved LLM error logging with full traceback.
- Optimized Vertex AI model and region defaults.
- Enhanced AI-based test generation with improved UI and backend support.
- Simplified schema wrapping logic in RhesisLLM.
- Refactored the metrics module for improved organization and maintainability.
- Updated supported file types for source extraction.

### Fixed
- Fixed Hugging Face imports.
- Fixed `_create_ollama_llm` initialization error.
- Corrected schema type hints in `RhesisLLM` and `VertexAILLM`.
- Corrected type hint in `validate_llm_response`.
- Corrected supported params for `RhesisPromptMetricCategorical`.
- Handled OpenAI-wrapped schemas in LLM providers.
- Fixed handling of missing DeepEval metrics in older versions.
- Fixed line length linting errors.
- Fixed various bugs in metrics and tests.
- Fixed issues with Ragas metrics initialization and usage.
- Fixed issues with DeepEval model initialization.
- Fixed UTF-8 encoding for markitdown text extraction.

### Removed
- Removed optional DeepEval metric imports.
- Removed unused `LLMService` class.
- Removed unnecessary markdown stripping in `LiteLLM`.
- Removed unused `NumericDetailedJudge` from factory.


## [0.3.1] - 2025-10-16

### Added
- Added support for user-defined LLM provider generation and execution.
- Enhanced `DocumentExtractor` with `BytesIO` support for processing documents from memory.
- Added `model` parameter support to the synthesizer factory, allowing specification of the LLM model to use.

### Changed
- Updated `ParaphrasingSynthesizer` to utilize the `model` parameter for LLM selection.
- Modernized SDK documentation with Rhesis AI branding.

### Fixed
- Corrected the class name for DeepEval context relevancy metrics.
- Resolved an issue related to worker-based generation.
- Fixed an issue where the `main` branch might be missing in the Makefile git diff.
- Fixed an error when pulling metrics.
- Removed `schema` from kwargs to resolve an issue.

### Removed
- (None)


## [0.3.0] - 2025-10-02

### Added
- Added `push` functionality to `PromptMetricCategorical` and `PromptMetricNumeric` for submitting metric data.
- Added `pull` functionality to `PromptMetricCategorical` and `PromptMetricNumeric` for retrieving metric data by name or ID.
- Added `from_config` method to `PromptMetric` for easier instantiation from configuration.
- Added `sdk_config_to_backend_config` and `backend_config_to_sdk_config` functions for configuration conversion.
- Added parameter and URL parameter processing in the SDK client.
- Added metrics endpoint to the SDK client.

### Changed
- Refactored metric backend to use Rhesis instead of native.
- Refactored common metric functionality into base classes.
- Improved metric configuration to accept enums.
- Improved configuration handling for metrics.
- Updated `BaseMetric` to accept enums for categorical metrics.

### Fixed
- Resolved linting errors in test_metric.py.
- Fixed default arguments for `prompt_metric_categorical`.
- Fixed metric backend configuration.
- Fixed enum and string validation in metrics.
- Fixed handling of categories in `PromptMetric`.
- Fixed raising errors for incorrect metric types.
- Fixed prompt metric imports.
- Fixed test data leakage in `test_metric.py`.
- Fixed handling of `None` config in prompt synthesizer.


## [0.2.4] - 2025-09-18

### Added
- Added `DocumentSynthesizer` for document text extraction and chunking, enabling the creation of context from documents.
- Added `ContextGenerator` service with semantic chunking for improved context selection.
- Added support for Ollama LLM provider.
- Added document source tracking to `DocumentSynthesizer`.
- Added `strategy` parameter to `DocumentSynthesizer` for sequential vs random context selection.
- Added comprehensive user feedback for test generation plan.

### Changed
- Refactored benchmarking framework to integrate SDK modules and improve model handling.
- Refactored `PromptSynthesizer` to use context instead of documents.
- Refactored `RhesisPromptMetric` for improved performance and maintainability.
- Updated `DocumentSynthesizer` to use `Document` dataclass instead of dictionaries.
- Updated LLM providers to inherit from LiteLLM for GeminiLLM and OpenAILLM.
- Improved model factory for easier model selection and configuration.
- Metrics now accept a model directly, allowing for more flexible model integration.
- Replaced `ContextSynthesizer` with `ContextGenerator` service.
- Enforced hard size limits with semantic-first splitting in `ContextGenerator`.

### Fixed
- Fixed batch size None comparison error.
- Fixed testset generation issues.
- Fixed minor issues in LLM provider implementations.
- Fixed template path for metrics.
- Fixed Python package version conflicts.

### Removed
- Removed `pyarrow` dependency to reduce environment and Docker image sizes.
- Removed the template caching mechanism.
- Removed binary and categorical functionality from prompt metrics.
- Removed the absolute_max_context_tokens limit.
- Removed document support from `PromptSynthesizer`.
- Removed the need for API keys in some configurations.


## [0.2.3] - 2025-09-04

### Added
- Support for JSON schema definitions in LLM service requests, allowing for structured responses.
- Integration with Gemini and OpenAI LLMs via the LLM service.
- API key handling for LLM providers.
- Basic tests for base LLM and model factory.
- Tests for SDK service utilities.

### Changed
- **Breaking Change:** Renamed `rhesis_provider` to `native`.
- **Breaking Change:** Renamed `openai_provider`.
- **Breaking Change:** Renamed `gemini`.
- **Breaking Change:** Renamed `factory`.
- **Breaking Change:** Renamed `rhesisllmservice`.
- Refactored LLM service architecture, including moving `basellm`, `utils`, and `modelfactory` to new locations.
- Renamed the `response_format` argument to `schema` for clarity and consistency.
- Improved code structure and cleanliness in Gemini and OpenAI providers.
- Updated linting process to use `uvx` instead of `uv run`.
- Refactored prompt synthesizers to use helper functions for code reuse and improved maintainability.
- Renamed 'document context' to the more generic 'context' in relevant components.

### Fixed
- Fixed a bug in the Rhesis (now Native) LLM service.
- Fixed issues with the Rhesis provider.

### Removed
- Removed `pip` from SDK dependencies.


## [0.2.2] - 2025-08-22

### Added
- Support for extracting content from `.docx`, `.pptx`, and `.xlsx` file formats.

### Changed
- Migrated document extraction from `docling` to `markitdown` for improved performance and format support.
- Improved code style and consistency across the SDK.
- Enhanced linting and formatting processes using `ruff` via Makefile improvements and a pre-commit hook at the root level.

### Removed
- Support for extracting content from `.url` and `.youtube` file extensions.


## [0.2.1] - 2025-08-08

### Added
- Added `get_field_names_from_schema` method to the `BaseEntity` class. This method retrieves field names from the OpenAPI schema, enabling dynamic access to entity properties.

### Changed
- Updated the default base URL for the API endpoint.

### Fixed
- Fixed an issue with the default base URL for API endpoint.

### Documentation
- Improved the readability and logical flow of the contributing guide.
- Enhanced the styling of the contributing guide for better user experience.


## [0.2.0] - 2025-07-25

### Added
- Added `documents` parameter to `PromptSynthesizer` for enhanced document handling.
- Added `DocumentExtractor` class with support for `.txt` files.
- Added synthesizer factory to SDK for easier synthesizer creation.
- Added custom behavior informed by prompt to `PromptSynthesizer`.

### Changed
- Adjusted `PromptSynthesizer` to allow custom behaviors.

### Fixed
- Corrected typos and formatting errors in documentation and code.

### Removed
- Removed tag creation from the release script.

### Documentation
- Updated `CONTRIBUTING.md` to include MacOS setup instructions.
- Updated general documentation.

- Ongoing development within the main repo structure
- Integration with other main repo components

## [0.1.9] - 2025-05-15

### Added
- Added rhesis namespace - now accessible via `rhesis.sdk`

### Changed
- Migrated to uv for package management, a more modern approach

## [0.1.8] - 2025-04-30 (Included in repository-wide v0.1.0 release)

### Added
- Support for custom test templates
- New paraphrasing capabilities
- Additional LLM service integrations
- Better documentation structure within Sphinx

### Changed
- Versioning in documentation is linked to source files in the code base

### Fixed
- Issue with token handling in the API client
- Performance improvements in test generation
- Documentation build issues that were generating warnings in Sphinx

## [0.1.7] - 2025-04-17

### Added
- Added test set upload functionality

### Changed
- Improved synthesizers and LLM generation functionality

### Fixed
- Fixed method naming issues

## [0.1.6] - 2025-04-14

### Added
- Added run method to LLM Service for improved convenience
- Added new Prompt and Test entity classes
- Added automatic test set description generation
- Added set_attributes() method to TestSet class
- Added support for custom system prompts in synthesizers

### Changed
- Changed TestSet to work with tests instead of prompts
- Changed synthesizers to use new test-focused entity model
- Changed prompt templates to match new test entity format

### Removed
- Removed direct prompt handling from TestSet class
- Removed old prompt-based test set generation

### Fixed
- Fixed synthesizer response parsing to handle new test structure
- Fixed test set property extraction to work with nested test objects

## [0.1.5] - 2025-02-21

### Added
- Added ParaphrasingSynthesizer for generating paraphrases of test cases

## [0.1.4] - 2025-02-20

### Added
- Added CLI scaffolding for rhesis

## [0.1.3] - 2025-02-19

### Added
- Added new test set capabilities
- Added PromptSynthesizer for generating test sets from prompts
- Added example usage for PromptSynthesizer

## [0.1.2] - 2025-02-18

### Added
- Added new topic entity
- Added base entity for CRUD testing
- Added topic tests

## [0.1.1] - 2025-02-17

### Added
- Added support for Parquet files
- Added more entities and functionality

## [0.1.0] - 2025-01-26

### Added
- Initial release of the SDK
- Core functionality for test set access
- Basic documentation and examples
- Basic unit tests and integration tests


[Unreleased]: https://github.com/rhesis-ai/rhesis/compare/sdk-v0.1.9...HEAD
[0.1.9]: https://github.com/rhesis-ai/rhesis/releases/tag/sdk-v0.1.9
[0.1.8]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.8
[0.1.7]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.7
[0.1.6]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.6
[0.1.5]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.5
[0.1.4]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.4
[0.1.3]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.3
[0.1.2]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.2
[0.1.1]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.1
[0.1.0]: https://github.com/rhesis-ai/rhesis-sdk/releases/tag/v0.1.0
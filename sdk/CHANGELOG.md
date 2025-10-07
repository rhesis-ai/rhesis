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
# Changelog

All notable changes to Rhesis Penelope will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Global tool execution limit** to prevent infinite loops. By default, limits total tool executions to `max_iterations × 5` (e.g., 10 turns × 5 = 50 executions).
- **Environment variable support** for configuring the execution multiplier via `PENELOPE_MAX_TOOL_EXECUTIONS_MULTIPLIER`.
- **Progress warnings** at 60% and 80% of execution limits to help developers tune limits before hitting hard stops.
- **Enhanced workflow validation** with same-tool repetition detection (blocks tools used 5+ times in last 6 executions).
- **Improved error messages** with actionable guidance when limits are reached, including execution statistics and instructions to increase limits.

### Changed
- **BREAKING**: Workflow validation failures now **block execution** instead of just logging warnings. This prevents known bad patterns (excessive consecutive analysis tools, repetitive tool usage) from causing infinite loops.
- **Increased consecutive analysis tool limit** from 3 to 5 for more flexibility in complex tests.
- **Stopping conditions** now check global execution limit first (before max iterations) to catch runaway executions early.

### Fixed
- Infinite loop scenarios where analysis tools could execute indefinitely without incrementing turn count.
- Cost explosion risks from unbounded tool executions.

## [0.1.0] - 2025-01-31

### Added
- Initial release of Penelope, the intelligent multi-turn testing agent
- Core `PenelopeAgent` class with transparent reasoning
- Base instructions following Anthropic's agent engineering principles
- Comprehensive tool system with Anthropic-quality ACI documentation:
  - `EndpointTool` for interacting with test endpoints
  - `AnalyzeTool` for analyzing responses
  - `ExtractTool` for extracting information
- Context and state management for multi-turn conversations
- Stopping conditions (max iterations, timeout, goal achievement)
- Rich console output with transparency mode
- Integration with Rhesis SDK LLM providers
- Extensible tool system for custom tools
- Comprehensive documentation and examples

### Features
- Multi-turn conversation testing
- Goal-oriented test execution
- Transparent reasoning at each step
- Tool-based interaction with ground truth feedback
- Support for all Rhesis SDK LLM providers
- Configurable stopping conditions
- Detailed test results with conversation history

### Documentation
- Complete README with usage examples
- CONTRIBUTING guide with development workflow
- Basic example demonstrating core functionality
- Extensively documented tools following ACI principles

### Dependencies
- `rhesis-sdk>=0.4.0` - Core Rhesis functionality
- `pydantic>=2.0.0` - Data validation
- `tenacity>=8.2.3` - Retry logic
- `rich>=13.0.0` - Console output
- `tiktoken>=0.9.0` - Token counting

[0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/penelope-v0.1.0



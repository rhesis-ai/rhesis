"""Exceptions for tool configuration and resolution errors."""


class ToolConfigurationError(Exception):
    """Raised when a tool cannot be resolved or its configuration is invalid.

    Covers both MCP and REST tool providers: tool not found, deleted,
    unsupported provider, invalid/missing credentials, or URL validation failure.
    """

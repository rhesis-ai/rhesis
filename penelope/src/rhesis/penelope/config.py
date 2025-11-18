"""
Penelope configuration module.

This module provides global configuration for Penelope that can be set via
environment variables or programmatically.
"""

import logging
import os
from typing import Optional


class PenelopeConfig:
    """
    Global configuration for Penelope.

    Configuration can be set via:
    1. Environment variables (PENELOPE_*)
    2. Programmatically via setter methods

    Configuration Options:
        - Log Level: DEBUG, INFO, WARNING, ERROR, CRITICAL
        - Default Model: Model provider (default: "vertex_ai")
        - Default Model Name: Specific model (default: "gemini-2.0-flash")
        - Default Max Iterations: Maximum turns before stopping (default: 10)

    Environment Variables:
        - PENELOPE_LOG_LEVEL: Set log level (default: INFO)
        - PENELOPE_DEFAULT_MODEL: Set model provider (default: vertex_ai)
        - PENELOPE_DEFAULT_MODEL_NAME: Set model name (default: gemini-2.0-flash)
        - PENELOPE_DEFAULT_MAX_ITERATIONS: Set max iterations (default: 10)

    Example:
        # Via environment variable
        export PENELOPE_LOG_LEVEL=DEBUG
        export PENELOPE_DEFAULT_MODEL=anthropic
        export PENELOPE_DEFAULT_MODEL_NAME=claude-4
        export PENELOPE_DEFAULT_MAX_ITERATIONS=30

        # Via code
        from rhesis.penelope import PenelopeConfig
        PenelopeConfig.set_log_level("DEBUG")
        PenelopeConfig.set_default_model("anthropic", "claude-4")
        PenelopeConfig.set_default_max_iterations(30)
    """

    # Default values
    _log_level: Optional[str] = None
    _default_model: Optional[str] = None
    _default_model_name: Optional[str] = None
    _default_max_iterations: Optional[int] = None
    _initialized: bool = False

    @classmethod
    def get_log_level(cls) -> str:
        """
        Get the log level for Penelope.

        Checks (in order):
        1. Programmatically set value
        2. PENELOPE_LOG_LEVEL env var
        3. Default: INFO

        Returns:
            Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if cls._log_level is not None:
            return cls._log_level

        return os.getenv("PENELOPE_LOG_LEVEL", "INFO").upper()

    @classmethod
    def get_default_model(cls) -> str:
        """
        Get the default model provider for Penelope.

        Checks (in order):
        1. Programmatically set value
        2. PENELOPE_DEFAULT_MODEL env var
        3. Default: "vertex_ai"

        Returns:
            Model provider string (e.g., "vertex_ai", "anthropic", "openai")
        """
        if cls._default_model is not None:
            return cls._default_model

        return os.getenv("PENELOPE_DEFAULT_MODEL", "rhesis")

    @classmethod
    def get_default_model_name(cls) -> str:
        """
        Get the default model name for Penelope.

        Checks (in order):
        1. Programmatically set value
        2. PENELOPE_DEFAULT_MODEL_NAME env var
        3. Default: "gemini-2.0-flash"

        Returns:
            Model name string (e.g., "gemini-2.0-flash", "claude-4")
        """
        if cls._default_model_name is not None:
            return cls._default_model_name

        return os.getenv("PENELOPE_DEFAULT_MODEL_NAME", "gemini-2.0-flash")

    @classmethod
    def get_default_max_iterations(cls) -> int:
        """
        Get the default max iterations for Penelope.

        Checks (in order):
        1. Programmatically set value
        2. PENELOPE_DEFAULT_MAX_ITERATIONS env var
        3. Default: 10

        Returns:
            Maximum number of iterations before stopping
        """
        if cls._default_max_iterations is not None:
            return cls._default_max_iterations

        env_value = os.getenv("PENELOPE_DEFAULT_MAX_ITERATIONS")
        if env_value is not None:
            try:
                return int(env_value)
            except ValueError:
                # Invalid value in env var, use default
                return 10

        return 10

    @classmethod
    def set_log_level(cls, level: str):
        """
        Programmatically set the log level.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        Note:
            - DEBUG: Shows all logs including from external libraries
            - INFO+: Suppresses external library debug logs
        """
        cls._log_level = level.upper()
        cls._apply_logging_config()

    @classmethod
    def set_default_model(cls, model: str, model_name: str):
        """
        Programmatically set the default model configuration.

        Args:
            model: Model provider (e.g., "vertex_ai", "anthropic", "openai")
            model_name: Specific model name (e.g., "gemini-2.0-flash", "claude-4")

        Example:
            >>> PenelopeConfig.set_default_model("anthropic", "claude-4")
        """
        cls._default_model = model
        cls._default_model_name = model_name

    @classmethod
    def set_default_max_iterations(cls, max_iterations: int):
        """
        Programmatically set the default max iterations.

        Args:
            max_iterations: Maximum number of turns before stopping (must be positive)

        Raises:
            ValueError: If max_iterations is not positive

        Example:
            >>> PenelopeConfig.set_default_max_iterations(30)
        """
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        cls._default_max_iterations = max_iterations

    @classmethod
    def initialize(cls):
        """
        Initialize Penelope configuration.

        This is called automatically when the module is imported,
        but can be called manually to re-apply configuration.
        """
        if cls._initialized:
            return

        cls._apply_logging_config()
        cls._initialized = True

    @classmethod
    def _apply_logging_config(cls):
        """Apply the current logging configuration."""
        log_level = cls.get_log_level()

        # Set Penelope's log level
        logging.getLogger("rhesis.penelope").setLevel(getattr(logging, log_level))

        # If not DEBUG, suppress verbose external library logs
        # DEBUG mode shows everything for troubleshooting
        if log_level != "DEBUG":
            cls._suppress_external_loggers()
        else:
            # In DEBUG mode, set external loggers to DEBUG as well
            cls._enable_external_loggers()

    @staticmethod
    def _suppress_external_loggers():
        """Suppress verbose logging from external libraries (INFO+ mode)."""
        external_loggers = [
            "LiteLLM",
            "httpx",
            "httpcore",
            "httpcore.connection",
            "httpcore.http11",
        ]

        for logger_name in external_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    @staticmethod
    def _enable_external_loggers():
        """Enable debug logging for external libraries (DEBUG mode)."""
        external_loggers = [
            "LiteLLM",
            "httpx",
            "httpcore",
            "httpcore.connection",
            "httpcore.http11",
        ]

        for logger_name in external_loggers:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)

    @classmethod
    def reset(cls):
        """Reset configuration to defaults (useful for testing)."""
        cls._log_level = None
        cls._default_model = None
        cls._default_model_name = None
        cls._default_max_iterations = None
        cls._initialized = False


# Initialize configuration on module import
PenelopeConfig.initialize()

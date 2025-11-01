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
    2. Programmatically via set_log_level()
    
    Log Levels:
        - DEBUG: Show all logs including from LiteLLM, httpx, httpcore
        - INFO: Show Penelope logs, suppress external library debug logs (default)
        - WARNING/ERROR/CRITICAL: Show only warnings and errors
    
    Example:
        # Via environment variable
        export PENELOPE_LOG_LEVEL=DEBUG
        
        # Via code
        from rhesis.penelope import PenelopeConfig
        PenelopeConfig.set_log_level("DEBUG")
    """
    
    # Default values
    _log_level: Optional[str] = None
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
        cls._initialized = False


# Initialize configuration on module import
PenelopeConfig.initialize()


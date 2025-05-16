"""Override the default logging module with a custom logger."""

from .rhesis_logger import logger

__all__ = ["logger"]

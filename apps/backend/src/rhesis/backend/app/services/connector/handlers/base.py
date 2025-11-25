"""Base handler class for SDK WebSocket message handlers."""

import logging
from abc import ABC
from typing import Any

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """Base class for SDK WebSocket message handlers."""

    def __init__(self):
        """Initialize the handler."""
        self.logger = logging.getLogger(self.__class__.__module__)

    def _log_handler_start(self, handler_name: str, message_type: str, **context) -> None:
        """Log the start of message handling."""
        self.logger.debug(f"[{handler_name}] Handling {message_type} message", extra=context)

    def _log_handler_error(self, handler_name: str, error: Exception, **context) -> None:
        """Log handler errors with context."""
        self.logger.error(
            f"[{handler_name}] Error handling message: {error}",
            exc_info=True,
            extra=context,
        )

    def _log_handler_success(self, handler_name: str, result: Any = None, **context) -> None:
        """Log successful message handling."""
        self.logger.debug(f"[{handler_name}] Successfully handled message", extra=context)

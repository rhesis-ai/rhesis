"""Pong message handler for SDK WebSocket connections."""

import logging

from .base import BaseHandler

logger = logging.getLogger(__name__)


class PongHandler(BaseHandler):
    """Handles pong messages from SDK WebSocket connections."""

    async def handle_pong_message(self, project_id: str, environment: str) -> None:
        """
        Handle pong message from SDK.

        Args:
            project_id: Project identifier
            environment: Environment name
        """
        self._log_handler_start(
            "PongHandler", 
            "pong", 
            project_id=project_id, 
            environment=environment
        )
        
        logger.debug(f"Received pong from {project_id}:{environment}")
        
        self._log_handler_success(
            "PongHandler",
            project_id=project_id,
            environment=environment
        )


# Global pong handler instance
pong_handler = PongHandler()

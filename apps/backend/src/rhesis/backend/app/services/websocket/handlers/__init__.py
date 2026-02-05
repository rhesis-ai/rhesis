"""WebSocket message handlers.

This module contains handlers for different WebSocket message types.
"""

from rhesis.backend.app.services.websocket.handlers.chat import handle_chat_message

__all__ = ["handle_chat_message"]

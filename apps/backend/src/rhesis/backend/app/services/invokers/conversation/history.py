"""Message history management for stateless multi-turn conversations."""

import copy
from typing import Dict, List, Optional


class MessageHistoryManager:
    """Manages accumulation of OpenAI-style conversation messages.

    Used for stateless endpoints that expect the full conversation history
    as a messages array in every request, rather than maintaining server-side
    session state.

    Note:
        This class is **not** thread-safe on its own.  When used via
        :class:`ConversationHistoryStore`, thread safety is provided by
        the store's internal lock.  Do not share instances across threads
        without external synchronization.

    Example usage:
        >>> history = MessageHistoryManager(system_prompt="You are helpful.")
        >>> history.add_user_message("Hello")
        >>> history.add_assistant_message("Hi! How can I help?")
        >>> history.add_user_message("What is 2+2?")
        >>> history.get_messages()
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"},
            {"role": "user", "content": "What is 2+2?"},
        ]
    """

    def __init__(self, system_prompt: Optional[str] = None) -> None:
        """Initialize the message history manager.

        Args:
            system_prompt: Optional system prompt to prepend as the first
                message with role "system". If None or empty, no system
                message is added.
        """
        self._messages: List[Dict[str, str]] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation history.

        Args:
            content: The user's message content.
        """
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation history.

        Args:
            content: The assistant's response content.
        """
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> List[Dict[str, str]]:
        """Return a deep copy of the accumulated messages.

        Returns:
            List of message dicts, each with 'role' and 'content' keys.
            Modifying the returned list does not affect the internal state.
        """
        return copy.deepcopy(self._messages)

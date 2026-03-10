"""Message history management for stateless multi-turn conversations."""

import copy
from typing import Any, Dict, List, Optional


class MessageHistoryManager:
    """Manages accumulation of OpenAI-style conversation messages.

    Used for stateless endpoints that expect the full conversation history
    as a messages array in every request, rather than maintaining server-side
    session state.

    Messages are stored as ``Dict[str, Any]`` to support the full OpenAI
    message format, including optional fields like ``tool_calls`` on
    assistant messages and ``tool_call_id`` on tool-role messages.

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
        self._messages: List[Dict[str, Any]] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation history.

        Args:
            content: The user's message content.
        """
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(
        self,
        content: str,
        *,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        **extra: Any,
    ) -> None:
        """Append an assistant message to the conversation history.

        Args:
            content: The assistant's response content.
            tool_calls: Optional list of OpenAI-format tool call objects.
                Only included in the message when not ``None``.
            **extra: Additional OpenAI-compatible fields to include on
                the message (e.g. ``name``, ``refusal``).
        """
        msg: Dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls is not None:
            msg["tool_calls"] = copy.deepcopy(tool_calls)
        for key, value in extra.items():
            if value is not None:
                msg[key] = value
        self._messages.append(msg)

    def add_message(self, message: Dict[str, Any]) -> None:
        """Append an arbitrary message dict to the conversation history.

        Use this for message types not covered by the convenience helpers,
        such as ``{"role": "tool", "tool_call_id": "...", "content": "..."}``.

        Args:
            message: A message dict.  Must contain at least a ``role`` key.

        Raises:
            ValueError: If the message dict does not contain a ``role`` key.
        """
        if "role" not in message:
            raise ValueError("Message dict must contain a 'role' key")
        self._messages.append(copy.deepcopy(message))

    def get_messages(self) -> List[Dict[str, Any]]:
        """Return a deep copy of the accumulated messages.

        Returns:
            List of message dicts.  Each dict contains at least ``role``
            and ``content`` keys, and may include additional fields such
            as ``tool_calls`` or ``tool_call_id``.
            Modifying the returned list does not affect the internal state.
        """
        return copy.deepcopy(self._messages)

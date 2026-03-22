"""
Standard message format types for conversational metrics.

These types follow the widely-adopted standard format compatible with:
- OpenAI API
- Anthropic API
- Vertex AI (Gemini)
- Azure OpenAI
- Most LLM providers
"""

import json
from typing import Any, Dict, Generator, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field


class UserMessage(BaseModel):
    """User message in standard format."""

    role: Literal["user"] = "user"
    content: str = Field(description="Text content of the message")

    model_config = ConfigDict(extra="allow")


class AssistantMessage(BaseModel):
    """
    Assistant message in standard format.
    Compatible with all major LLM providers.
    """

    role: Literal["assistant"] = "assistant"
    content: Optional[str] = Field(default=None, description="Text content of the message")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Tool calls made in this message"
    )
    context: Optional[List[Any]] = Field(
        default=None,
        description="Retrieval context returned by the endpoint (e.g. RAG sources)",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured metadata returned by the endpoint",
    )

    model_config = ConfigDict(extra="allow")


class ToolMessage(BaseModel):
    """Tool result message in standard format."""

    role: Literal["tool"] = "tool"
    tool_call_id: str = Field(description="The ID of the tool call this is responding to")
    name: str = Field(description="The name of the tool that was called")
    content: str = Field(description="The result of the tool call")

    model_config = ConfigDict(extra="allow")


class SystemMessage(BaseModel):
    """System message in standard format."""

    role: Literal["system"] = "system"
    content: str = Field(description="Text content of the message")

    model_config = ConfigDict(extra="allow")


# Union type for all standard messages
StandardMessage = Union[UserMessage, AssistantMessage, ToolMessage, SystemMessage]


class ConversationHistory(BaseModel):
    """
    Complete conversation history using standard message format.

    Accepts messages as:
    - Pydantic models (UserMessage, AssistantMessage, etc.)
    - Dicts in standard format ({"role": "user", "content": "..."})

    This format is compatible with all major LLM providers.
    """

    messages: List[Union[StandardMessage, Dict[str, Any]]] = Field(
        description="List of conversation messages in standard format"
    )
    conversation_id: Optional[str] = Field(default=None, description="Optional unique identifier")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata (goal, instructions, context, etc.)",
    )

    @classmethod
    def from_messages(
        cls, messages: List[Union[StandardMessage, Dict[str, Any]]], **kwargs
    ) -> "ConversationHistory":
        """
        Create from list of messages in standard format.

        Accepts:
        - Pydantic message objects
        - Dicts with role/content
        - Mix of both
        """
        return cls(messages=messages, **kwargs)

    @staticmethod
    def _msg_attrs(msg: Any) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        """Normalise a message (dict or typed model) to (role, content, metadata)."""
        if isinstance(msg, dict):
            return msg.get("role", ""), msg.get("content", ""), msg.get("metadata")
        return msg.role, msg.content or "", getattr(msg, "metadata", None)

    @staticmethod
    def _msg_context(msg: Any) -> Optional[List[Any]]:
        """Extract retrieval context from a message (dict or typed model)."""
        if isinstance(msg, dict):
            return msg.get("context")
        return getattr(msg, "context", None)

    @staticmethod
    def _msg_tool_calls(msg: Any) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from a message (dict or typed model)."""
        if isinstance(msg, dict):
            return msg.get("tool_calls")
        return getattr(msg, "tool_calls", None)

    def _iter_turns(
        self,
    ) -> Generator[Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]], None, None]:
        """
        Yield (user_content, assistant_content, assistant_metadata) for each turn.

        Groups consecutive user+assistant message pairs. Standalone assistant
        messages (no preceding user) are yielded with user_content=None.
        Non-user/assistant messages (system, tool) are skipped.
        """
        messages = self.messages
        i = 0
        while i < len(messages):
            role, content, _ = self._msg_attrs(messages[i])
            if not content:
                i += 1
                continue
            if role == "user":
                if i + 1 < len(messages):
                    nxt_role, nxt_content, nxt_meta = self._msg_attrs(messages[i + 1])
                    if nxt_role == "assistant" and nxt_content:
                        yield (content, nxt_content, nxt_meta)
                        i += 2
                        continue
                yield (content, None, None)
                i += 1
            elif role == "assistant":
                _, _, meta = self._msg_attrs(messages[i])
                yield (None, content, meta)
                i += 1
            else:
                i += 1

    def get_simple_turns(self) -> List[Dict[str, str]]:
        """
        Extract simple role/content pairs for metrics that don't need full format.

        Returns:
            List of {"role": str, "content": str} dicts
        """
        simple_turns = []
        for msg in self.messages:
            role, content, _ = self._msg_attrs(msg)
            if content:
                simple_turns.append({"role": role, "content": content})
        return simple_turns

    def get_assistant_metadata(self) -> List[Optional[Dict[str, Any]]]:
        """
        Extract per-turn metadata from assistant messages.

        Returns a list indexed to user+assistant exchange pairs (same indexing
        as get_simple_turns() groups). Returns None for turns where the endpoint
        returned no metadata.
        """
        return [meta for _, _, meta in self._iter_turns()]

    def get_assistant_context(self) -> List[Optional[List[Any]]]:
        """
        Extract per-turn retrieval context from assistant messages.

        Returns a list indexed to user+assistant exchange pairs. Returns None
        for turns where the endpoint returned no context.
        """
        contexts = []
        messages = self.messages
        i = 0
        while i < len(messages):
            role, content, _ = self._msg_attrs(messages[i])
            if not content:
                i += 1
                continue
            if role == "user":
                if i + 1 < len(messages):
                    nxt_role, nxt_content, _ = self._msg_attrs(messages[i + 1])
                    if nxt_role == "assistant" and nxt_content:
                        contexts.append(self._msg_context(messages[i + 1]))
                        i += 2
                        continue
                contexts.append(None)
                i += 1
            elif role == "assistant":
                contexts.append(self._msg_context(messages[i]))
                i += 1
            else:
                i += 1
        return contexts

    def get_assistant_tool_calls(self) -> List[Optional[List[Dict[str, Any]]]]:
        """
        Extract per-turn tool calls from assistant messages.

        Returns a list indexed to user+assistant exchange pairs. Returns None
        for turns where the endpoint returned no tool calls.
        """
        tool_calls_list: List[Optional[List[Dict[str, Any]]]] = []
        messages = self.messages
        i = 0
        while i < len(messages):
            role, content, _ = self._msg_attrs(messages[i])
            if not content:
                i += 1
                continue
            if role == "user":
                if i + 1 < len(messages):
                    nxt_role, nxt_content, _ = self._msg_attrs(messages[i + 1])
                    if nxt_role == "assistant" and nxt_content:
                        tool_calls_list.append(self._msg_tool_calls(messages[i + 1]))
                        i += 2
                        continue
                tool_calls_list.append(None)
                i += 1
            elif role == "assistant":
                tool_calls_list.append(self._msg_tool_calls(messages[i]))
                i += 1
            else:
                i += 1
        return tool_calls_list

    @staticmethod
    def _msg_is_renderable(msg: Any) -> bool:
        """Return True if the message has anything worth rendering.

        For assistant messages, tool_calls, metadata, or context are considered
        renderable even when the text content is empty or None. This prevents
        tool-call-only turns (content=None, tool_calls=[...]) from being silently
        dropped during formatting.

        For all other roles, non-empty text content is required.
        """
        role, content, metadata = ConversationHistory._msg_attrs(msg)
        if content:
            return True
        if role == "assistant":
            return bool(
                metadata
                or ConversationHistory._msg_context(msg)
                or ConversationHistory._msg_tool_calls(msg)
            )
        return False

    def format_conversation(self) -> str:
        """
        Return a structured transcript with numbered turns and inline metadata.

        Groups consecutive user/assistant message pairs into numbered turns.
        When an assistant message carries metadata, context, or tool calls they
        are rendered inline beneath the assistant response.

        Assistant messages with no text content but with tool_calls, metadata,
        or context are included — only the ``Assistant:`` text line is omitted
        for such messages so the structured fields are still visible.

        Example output::

            Turn 1:
              User: Hello
              Assistant: Hi there
              Metadata: {"intent": "greeting"}

            Turn 2:
              User: Search for X
              Tool Calls: [{"name": "search", "arguments": {"q": "X"}}]

        Use this method when the formatted text will be sent to an LLM judge so
        that metadata remains contextually tied to its turn.
        """
        formatted_turns = []
        turn_number = 0
        messages = self.messages
        i = 0

        while i < len(messages):
            role, content, _ = self._msg_attrs(messages[i])

            if not self._msg_is_renderable(messages[i]):
                i += 1
                continue

            if role == "user":
                turn_number += 1
                lines = [f"Turn {turn_number}:", f"  User: {content}"]
                if i + 1 < len(messages) and self._msg_is_renderable(messages[i + 1]):
                    nxt_role, nxt_content, nxt_meta = self._msg_attrs(messages[i + 1])
                    if nxt_role == "assistant":
                        if nxt_content:
                            lines.append(f"  Assistant: {nxt_content}")
                        nxt_ctx = self._msg_context(messages[i + 1])
                        if nxt_ctx:
                            lines.append(f"  Context: {json.dumps(nxt_ctx, indent=2)}")
                        if nxt_meta:
                            lines.append(f"  Metadata: {json.dumps(nxt_meta, indent=2)}")
                        nxt_tc = self._msg_tool_calls(messages[i + 1])
                        if nxt_tc:
                            lines.append(f"  Tool Calls: {json.dumps(nxt_tc, indent=2)}")
                        i += 2
                    else:
                        i += 1
                else:
                    i += 1
                formatted_turns.append("\n".join(lines))

            elif role == "assistant":
                turn_number += 1
                _, _, meta = self._msg_attrs(messages[i])
                ctx = self._msg_context(messages[i])
                tc = self._msg_tool_calls(messages[i])
                lines = [f"Turn {turn_number}:"]
                if content:
                    lines.append(f"  Assistant: {content}")
                if ctx:
                    lines.append(f"  Context: {json.dumps(ctx, indent=2)}")
                if meta:
                    lines.append(f"  Metadata: {json.dumps(meta, indent=2)}")
                if tc:
                    lines.append(f"  Tool Calls: {json.dumps(tc, indent=2)}")
                formatted_turns.append("\n".join(lines))
                i += 1

            else:
                formatted_turns.append(f"[{role}]: {content}")
                i += 1

        return "\n\n".join(formatted_turns)

    def to_text(self) -> str:
        """
        Return a flat transcript of the conversation as role-prefixed lines.

        Example output::

            User: Hello
            Assistant: Hi there

            User: How are you?
            Assistant: I'm fine

        Only messages with content are included. The role is title-cased
        (e.g. "user" → "User", "assistant" → "Assistant").
        Metadata, context, and tool calls are excluded — use format_conversation()
        when those fields need to be visible to an LLM judge.
        """
        parts = []
        for msg in self.messages:
            role, content, _ = self._msg_attrs(msg)
            if content:
                parts.append(f"{role.capitalize()}: {content}")
        return "\n\n".join(parts)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert all messages to dict format."""
        result: List[Dict[str, Any]] = []
        for msg in self.messages:
            if isinstance(msg, dict):
                result.append(msg)
            else:
                result.append(msg.model_dump())
        return result

    def __len__(self) -> int:
        """Return number of messages in conversation."""
        return len(self.messages)

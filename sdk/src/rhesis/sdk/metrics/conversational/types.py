"""
Standard message format types for conversational metrics.

These types follow the widely-adopted standard format compatible with:
- OpenAI API
- Anthropic API
- Vertex AI (Gemini)
- Azure OpenAI
- Most LLM providers
"""

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
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional per-turn metadata returned by the endpoint (e.g. RAG context)",
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
        """
        parts = []
        for msg in self.messages:
            role, content, _ = self._msg_attrs(msg)
            if content:
                parts.append(f"{role.capitalize()}: {content}")
        return "\n".join(parts)

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

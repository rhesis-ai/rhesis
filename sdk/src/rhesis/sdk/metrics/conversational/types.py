"""
Standard message format types for conversational metrics.

These types follow the widely-adopted standard format compatible with:
- OpenAI API
- Anthropic API
- Vertex AI (Gemini)
- Azure OpenAI
- Most LLM providers
"""

from typing import Any, Dict, List, Literal, Optional, Union

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

    def get_simple_turns(self) -> List[Dict[str, str]]:
        """
        Extract simple role/content pairs for metrics that don't need full format.

        Returns:
            List of {"role": str, "content": str} dicts
        """
        simple_turns = []
        for msg in self.messages:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
            else:
                role = msg.role
                content = msg.content or ""

            if content:  # Only include messages with content
                simple_turns.append({"role": role, "content": content})

        return simple_turns

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

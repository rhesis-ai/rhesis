"""
Pydantic schemas for structured outputs in Penelope.

These schemas enable structured output from LLMs, eliminating the need
for text parsing and making tool calls more reliable.

Note: Base message types (UserMessage, SystemMessage) are imported from SDK.
Penelope extends AssistantMessage and ToolMessage with strongly-typed tool calls
for better type safety in the agent loop.
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# Import base conversation types from SDK
from rhesis.sdk.metrics.conversational import (
    ConversationHistory,
    SystemMessage,
    UserMessage,
)

# Penelope-specific: Strongly-typed tool call structures
# These provide better type safety than SDK's generic Dict[str, Any] approach


class FunctionCall(BaseModel):
    """Function call specification in standard message format."""

    name: str = Field(description="The name of the function to call")
    arguments: str = Field(description="The arguments to pass to the function, as a JSON string")


class MessageToolCall(BaseModel):
    """Tool call specification in standard message format."""

    id: str = Field(description="Unique identifier for this tool call")
    type: Literal["function"] = Field(default="function", description="The type of tool call")
    function: FunctionCall = Field(description="The function to call")


class AssistantMessage(BaseModel):
    """
    Assistant message with strongly-typed tool calls.

    Extends SDK's base AssistantMessage with Pydantic-validated tool call structure
    for better type safety in Penelope's agent loop.
    """

    role: Literal["assistant"] = Field(default="assistant", description="Message role")
    content: Optional[str] = Field(default=None, description="Text content of the message")
    tool_calls: Optional[List[MessageToolCall]] = Field(
        default=None, description="Tool calls made in this message"
    )

    model_config = ConfigDict(extra="allow")


class ToolMessage(BaseModel):
    """
    Tool response message.

    Compatible with OpenAI message format and other major LLM providers.
    """

    role: Literal["tool"] = Field(default="tool", description="Message role")
    tool_call_id: str = Field(description="The ID of the tool call this is responding to")
    name: str = Field(description="The name of the tool that was called")
    content: str = Field(description="The result of the tool call, as a string")

    model_config = ConfigDict(extra="allow")


# Re-export for convenience
__all__ = [
    # SDK conversation types
    "ConversationHistory",
    "UserMessage",
    "SystemMessage",
    # Penelope message types (strongly-typed tool calls)
    "AssistantMessage",
    "ToolMessage",
    "FunctionCall",
    "MessageToolCall",
    # Penelope tool parameter schemas
    "SendMessageParams",
    "AnalyzeResponseParams",
    "ExtractInformationParams",
    "ToolCall",
]

# Tool Parameter Schemas


class SendMessageParams(BaseModel):
    """Parameters for send_message_to_target tool."""

    message: str = Field(description="The message to send to the target")
    session_id: Optional[str] = Field(
        default=None, description="Optional session ID for multi-turn conversations"
    )
    conversation_id: Optional[str] = Field(
        default=None, description="Optional conversation ID for multi-turn conversations"
    )
    thread_id: Optional[str] = Field(
        default=None, description="Optional thread ID for multi-turn conversations"
    )
    chat_id: Optional[str] = Field(
        default=None, description="Optional chat ID for multi-turn conversations"
    )
    dialog_id: Optional[str] = Field(
        default=None, description="Optional dialog ID for multi-turn conversations"
    )
    dialogue_id: Optional[str] = Field(
        default=None, description="Optional dialogue ID for multi-turn conversations"
    )
    context_id: Optional[str] = Field(
        default=None, description="Optional context ID for multi-turn conversations"
    )
    interaction_id: Optional[str] = Field(
        default=None, description="Optional interaction ID for multi-turn conversations"
    )

    def get_conversation_field_value(self) -> tuple[Optional[str], Optional[str]]:
        """
        Get the first non-None, non-empty conversation field and its value.

        Returns:
            Tuple of (field_name, field_value) or (None, None) if no conversation field is set
        """
        conversation_fields = [
            ("conversation_id", self.conversation_id),
            ("session_id", self.session_id),
            ("thread_id", self.thread_id),
            ("chat_id", self.chat_id),
            ("dialog_id", self.dialog_id),
            ("dialogue_id", self.dialogue_id),
            ("context_id", self.context_id),
            ("interaction_id", self.interaction_id),
        ]

        for field_name, field_value in conversation_fields:
            if field_value is not None and field_value != "":
                return field_name, field_value

        return None, None


class AnalyzeResponseParams(BaseModel):
    """Parameters for analyze_response tool."""

    response_text: str = Field(description="The response text to analyze")
    analysis_focus: str = Field(description="What to focus on in the analysis")
    context: Optional[str] = Field(default=None, description="Optional context for the analysis")


class ExtractInformationParams(BaseModel):
    """Parameters for extract_information tool."""

    response_text: str = Field(description="The response text to extract information from")
    extraction_target: str = Field(description="What specific information to extract")


class ToolCallItem(BaseModel):
    """A single tool call within a response."""

    tool_name: str = Field(
        description=(
            "The exact name of the tool to use. Must match one of the available tools. "
            "See ToolType enum in context.py for complete list of available tools "
            "and their descriptions."
        )
    )

    parameters: Union[SendMessageParams, AnalyzeResponseParams, ExtractInformationParams] = Field(
        description=(
            "Tool-specific parameters. Structure depends on tool_name:\n"
            "- send_message_to_target: {message: str, conversation_field: Optional[str]} "
            "(conversation_field can be session_id, conversation_id, thread_id, chat_id, etc.)\n"
            "- analyze_response: {response_text: str, analysis_focus: str, "
            "context: Optional[str]}\n"
            "- extract_information: {response_text: str, extraction_target: str}"
        )
    )


class ToolCall(BaseModel):
    """
    Structured output schema for agent tool calls.

    Supports one or more tool calls in a single response. Each tool is executed
    in sequence. The turn completes when a target interaction tool is executed.
    """

    reasoning: str = Field(
        description=(
            "Explain your thinking for this turn. What are you trying to accomplish? "
            "Why is this action appropriate given the test goal and previous results? "
            "If using multiple tools, explain the sequence and why each is needed."
        )
    )

    tool_calls: List[ToolCallItem] = Field(
        min_length=1,
        description=(
            "One or more tool calls to execute in sequence. Each tool will be executed "
            "in order. The turn completes when a target interaction tool is executed."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": (
                "Every tool call MUST include properly structured parameters "
                "matching the tool type."
            ),
            "examples": [
                {
                    "reasoning": (
                        "I need to test the chatbot's ability to handle basic "
                        "insurance questions. Starting with a general question "
                        "about available types."
                    ),
                    "tool_name": "send_message_to_target",
                    "parameters": {
                        "message": "What types of insurance do you offer?",
                        "session_id": None,
                    },
                },
                {
                    "reasoning": (
                        "The chatbot listed several insurance types. I'll follow up "
                        "by asking about auto insurance to test context maintenance."
                    ),
                    "tool_name": "send_message_to_target",
                    "parameters": {
                        "message": "Tell me more about auto insurance",
                        "session_id": "abc-123",
                    },
                },
                {
                    "reasoning": (
                        "I want to analyze the chatbot's previous response "
                        "for tone and professionalism."
                    ),
                    "tool_name": "analyze_response",
                    "parameters": {
                        "response_text": "The chatbot's response here...",
                        "analysis_focus": "Evaluate tone and professionalism",
                        "context": None,
                    },
                },
            ],
        }
    )

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
    UserMessage,
    SystemMessage,
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


class AnalyzeResponseParams(BaseModel):
    """Parameters for analyze_response tool."""

    response_text: str = Field(description="The response text to analyze")
    analysis_focus: str = Field(description="What to focus on in the analysis")
    context: Optional[str] = Field(default=None, description="Optional context for the analysis")


class ExtractInformationParams(BaseModel):
    """Parameters for extract_information tool."""

    response_text: str = Field(description="The response text to extract information from")
    extraction_target: str = Field(description="What specific information to extract")


class ToolCall(BaseModel):
    """
    Structured output schema for agent tool calls.

    This schema ensures the LLM returns properly formatted tool calls
    that can be directly executed without parsing.
    """

    reasoning: str = Field(
        description=(
            "Explain your thinking for this turn. What are you trying to accomplish? "
            "Why is this action appropriate given the test goal and previous results?"
        )
    )

    tool_name: str = Field(
        description=(
            "The exact name of the tool to use. Must match one of the available tools: "
            "send_message_to_target, analyze_response, extract_information"
        )
    )

    parameters: Union[SendMessageParams, AnalyzeResponseParams, ExtractInformationParams] = Field(
        description=(
            "Tool-specific parameters. Structure depends on tool_name:\n"
            "- send_message_to_target: {message: str, session_id: Optional[str]}\n"
            "- analyze_response: {response_text: str, analysis_focus: str, "
            "context: Optional[str]}\n"
            "- extract_information: {response_text: str, extraction_target: str}"
        )
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

"""
Pydantic schemas for structured outputs in Penelope.

These schemas enable structured output from LLMs, eliminating the need
for text parsing and making tool calls more reliable.

Includes standard message format schemas (compatible with OpenAI format)
for maximum LLM provider compatibility.
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# Standard Message Format (OpenAI-compatible)


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
    Assistant message with optional tool calls.

    Compatible with OpenAI message format and other major LLM providers.
    """

    role: Literal["assistant"] = Field(default="assistant", description="Message role")
    content: Optional[str] = Field(default=None, description="Text content of the message")
    tool_calls: Optional[List[MessageToolCall]] = Field(
        default=None, description="Tool calls made in this message"
    )

    model_config = ConfigDict(
        extra="allow"
    )  # Allow additional fields for provider-specific extensions


class ToolMessage(BaseModel):
    """
    Tool response message.

    Compatible with OpenAI message format and other major LLM providers.
    """

    role: Literal["tool"] = Field(default="tool", description="Message role")
    tool_call_id: str = Field(description="The ID of the tool call this is responding to")
    name: str = Field(description="The name of the tool that was called")
    content: str = Field(description="The result of the tool call, as a string")

    model_config = ConfigDict(
        extra="allow"
    )  # Allow additional fields for provider-specific extensions


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


class CriterionEvaluation(BaseModel):
    """Evaluation of a single goal criterion."""

    criterion: str = Field(description="The specific criterion being evaluated")
    met: bool = Field(description="Whether this criterion was met")
    evidence: str = Field(description="Specific evidence from the conversation for this criterion")


class SimpleGoalEval(BaseModel):
    """
    Schema for interim goal achievement evaluation.

    This is a temporary schema used until SDK multi-turn metrics are available.
    It provides structured output for LLM-based goal evaluation.

    The schema forces criterion-by-criterion evaluation for reliability.
    """

    turn_count: int = Field(
        description=(
            "CRITICAL: Count the actual number of user-assistant exchanges "
            "in the conversation. Each USER message followed by an ASSISTANT "
            "response = 1 turn."
        )
    )
    criteria_evaluations: list[CriterionEvaluation] = Field(
        description="Evaluation of each specific criterion mentioned in the goal. "
        "Break down the goal into individual measurable criteria."
    )
    all_criteria_met: bool = Field(
        description="True only if ALL criteria evaluations have met=True"
    )
    goal_achieved: bool = Field(
        description="Overall assessment: True if all_criteria_met AND no critical issues found"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the assessment (0.0 to 1.0)"
    )
    reasoning: str = Field(description="Brief summary explaining the overall assessment")
    evidence: list[str] = Field(
        default_factory=list,
        description="Key quotes or observations supporting the overall assessment",
    )


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

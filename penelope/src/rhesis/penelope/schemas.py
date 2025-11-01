"""
Pydantic schemas for structured outputs in Penelope.

These schemas enable structured output from LLMs, eliminating the need
for text parsing and making tool calls more reliable.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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
    
    parameters: Dict[str, Any] = Field(
        description=(
            "Parameters to pass to the tool as a JSON object. "
            "REQUIRED for send_message_to_target: must include 'message' key with the text to send. "
            "Example: {\"message\": \"What types of insurance do you offer?\", \"session_id\": null}"
        ),
        default_factory=dict
    )
    
    class Config:
        json_schema_extra = {
            "description": "Every tool call MUST include the parameters field with appropriate values.",
            "examples": [
                {
                    "reasoning": "I need to test the chatbot's ability to handle basic insurance questions. Starting with a general question about available types.",
                    "tool_name": "send_message_to_target",
                    "parameters": {
                        "message": "What types of insurance do you offer?"
                    }
                },
                {
                    "reasoning": "The chatbot listed several insurance types. I'll follow up by asking about auto insurance to test context maintenance.",
                    "tool_name": "send_message_to_target",
                    "parameters": {
                        "message": "Tell me more about auto insurance",
                        "session_id": "abc-123"
                    }
                },
                {
                    "reasoning": "I want to analyze the chatbot's previous response for tone and professionalism.",
                    "tool_name": "analyze_response",
                    "parameters": {
                        "response_text": "The chatbot's response here...",
                        "analysis_focus": "Evaluate tone and professionalism"
                    }
                }
            ]
        }



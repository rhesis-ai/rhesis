"""
Turn execution module for Penelope.

This module handles the execution of individual turns in the agent loop,
including LLM interaction, tool invocation, and state updates.
"""

import json
import logging
from typing import List

from rhesis.penelope.context import TestState
from rhesis.penelope.prompts import FIRST_TURN_PROMPT, SUBSEQUENT_TURN_PROMPT
from rhesis.penelope.schemas import AssistantMessage, FunctionCall, MessageToolCall, ToolCall, ToolMessage
from rhesis.penelope.tools.base import Tool
from rhesis.penelope.utils import display_turn
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class TurnExecutor:
    """
    Handles execution of individual turns in the agent loop.

    Responsibilities:
    - Generate LLM responses with tool calls
    - Execute tools based on LLM decisions
    - Update test state with turn results
    - Display turn information (if verbose)

    Args:
        model: Language model for generating responses
        verbose: Whether to print detailed execution information
        enable_transparency: Whether to show reasoning at each step
    """

    def __init__(
        self,
        model: BaseLLM,
        verbose: bool = False,
        enable_transparency: bool = True,
    ):
        """Initialize the turn executor."""
        self.model = model
        self.verbose = verbose
        self.enable_transparency = enable_transparency

    def execute_turn(
        self,
        state: TestState,
        tools: List[Tool],
        system_prompt: str,
    ) -> bool:
        """
        Execute one turn of the agent loop.

        Args:
            state: Current test state
            tools: Available tools
            system_prompt: System prompt for the LLM

        Returns:
            True if turn executed successfully, False if should stop
        """
        # Build conversation history (native Pydantic messages)
        conversation_messages = state.get_conversation_messages()

        # Create user prompt for this turn
        if state.current_turn == 0:
            user_prompt = FIRST_TURN_PROMPT.render()
        else:
            user_prompt = SUBSEQUENT_TURN_PROMPT.render()

        # Get model response
        try:
            # Build messages for the model
            if conversation_messages:
                # We have history, use it
                prompt = user_prompt
                for msg in conversation_messages[-10:]:  # Last 10 messages (5 turns) for context
                    prompt += f"\n\n{msg.role}: {msg.content}"
            else:
                prompt = user_prompt

            response = self.model.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                schema=ToolCall,  # Use Pydantic schema for structured output
            )

        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            state.add_finding(f"Error: Model generation failed - {str(e)}")
            return False

        # Extract values from structured response (no parsing needed!)
        # Type narrowing: response should be dict when schema is provided
        if not isinstance(response, dict):
            logger.error(f"Expected dict response, got {type(response)}")
            state.add_finding(f"Error: Invalid model response type - {type(response)}")
            return False
            
        reasoning = response.get("reasoning", "")
        action_name = response.get("tool_name", "")
        params_obj = response.get("parameters", {})

        # Convert Pydantic model to dict if needed
        if hasattr(params_obj, "model_dump"):
            # It's a Pydantic model, convert to dict
            action_params = params_obj.model_dump(exclude_none=True)
        elif isinstance(params_obj, dict):
            # Already a dict (shouldn't happen with proper schema, but handle it)
            action_params = params_obj
        else:
            # Unexpected type
            logger.warning(f"Unexpected parameters type: {type(params_obj)}")
            action_params = {}

        # Debug: Log structured response
        if self.verbose:
            logger.debug(f"Structured response - Tool: {action_name}, Params: {action_params}")

        # With structured output, we should always have an action
        if not action_name:
            logger.warning("Structured output missing tool_name")
            action_name = "no_action"
            action_params = {}

        # Create assistant message with tool_calls (Pydantic)
        tool_call_id = f"call_{state.current_turn + 1}_{action_name}"
        assistant_message = AssistantMessage(
            content=reasoning,
            tool_calls=[
                MessageToolCall(
                    id=tool_call_id,
                    type="function",
                    function=FunctionCall(
                        name=action_name,
                        arguments=json.dumps(action_params),
                    ),
                )
            ],
        )

        # Find and execute the tool
        tool_result = None
        for tool in tools:
            if tool.name == action_name:
                if self.verbose:
                    logger.info(f"Executing tool: {action_name} with params: {action_params}")

                tool_result = tool.execute(**action_params)
                break

        if tool_result is None:
            # Tool not found
            tool_result_dict = {
                "success": False,
                "output": {},
                "error": f"Unknown tool: {action_name}",
            }
        else:
            tool_result_dict = {
                "success": tool_result.success,
                "output": tool_result.output,
                "error": tool_result.error,
            }

        # Create tool response message (Pydantic)
        tool_message = ToolMessage(
            tool_call_id=tool_call_id,
            name=action_name,
            content=json.dumps(tool_result_dict),
        )

        # Add turn to state using native OpenAI format
        state.add_turn(
            reasoning=reasoning,
            assistant_message=assistant_message,
            tool_message=tool_message,
        )

        # Display turn if verbose
        if self.verbose and self.enable_transparency:
            display_turn(state.current_turn, reasoning, action_name, tool_result_dict)

        return True


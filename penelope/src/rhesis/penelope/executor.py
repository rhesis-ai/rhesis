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
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    ToolCall,
    ToolMessage,
)
from rhesis.penelope.tools.base import Tool
from rhesis.penelope.utils import display_turn
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class ResponseParser:
    """Robust parser for LLM responses with validation."""
    
    @staticmethod
    def parse_tool_calls(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse tool calls from response with validation.
        
        Args:
            response: Raw LLM response dictionary
            
        Returns:
            List of validated tool call dictionaries
            
        Raises:
            ValueError: If response format is invalid
        """
        if not isinstance(response, dict):
            raise ValueError(f"Expected dict response, got {type(response)}")
        
        tool_calls_data = response.get("tool_calls", [])
        if not tool_calls_data:
            raise ValueError("No tool calls found in response")
        
        if not isinstance(tool_calls_data, list):
            raise ValueError(f"Expected tool_calls to be list, got {type(tool_calls_data)}")
        
        validated_calls = []
        for i, tool_call in enumerate(tool_calls_data):
            validated_call = ResponseParser._validate_tool_call(tool_call, i)
            validated_calls.append(validated_call)
        
        return validated_calls
    
    @staticmethod
    def _validate_tool_call(tool_call: Any, index: int) -> Dict[str, Any]:
        """Validate a single tool call."""
        if not isinstance(tool_call, dict):
            raise ValueError(f"Tool call {index} must be dict, got {type(tool_call)}")
        
        tool_name = tool_call.get("tool_name")
        if not tool_name or not isinstance(tool_name, str):
            raise ValueError(f"Tool call {index} missing or invalid tool_name")
        
        parameters = tool_call.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError(f"Tool call {index} parameters must be dict, got {type(parameters)}")
        
        return {
            "tool_name": tool_name,
            "parameters": parameters
        }


class ToolCallIdGenerator:
    """Generates unique tool call IDs with configurable format."""
    
    @staticmethod
    def generate_id(execution_count: int, tool_name: str, format_template: str = "call_{count}_{tool}") -> str:
        """
        Generate a tool call ID.
        
        Args:
            execution_count: Current execution count
            tool_name: Name of the tool being called
            format_template: Template string with {count} and {tool} placeholders
            
        Returns:
            Formatted tool call ID
        """
        return format_template.format(count=execution_count + 1, tool=tool_name)
    
    @staticmethod
    def generate_uuid_id(tool_name: str) -> str:
        """Generate a UUID-based tool call ID for guaranteed uniqueness."""
        import uuid
        return f"{tool_name}_{uuid.uuid4().hex[:8]}"


class ContextManager:
    """Manages conversation context with intelligent selection."""
    
    @staticmethod
    def select_context_messages(
        messages: List[Any], 
        max_messages: int = None,
        max_tokens: int = None,
        strategy: str = "recent"
    ) -> List[Any]:
        """
        Select context messages based on strategy and limits.
        
        Args:
            messages: All conversation messages
            max_messages: Maximum number of messages to include
            max_tokens: Maximum token count (if supported)
            strategy: Selection strategy ("recent", "relevant", "balanced")
            
        Returns:
            Selected context messages
        """
        if not messages:
            return []
        
        if max_messages is None:
            from rhesis.penelope.config import PenelopeConfig
            max_messages = PenelopeConfig.DEFAULT_CONTEXT_WINDOW_MESSAGES
        
        if strategy == "recent":
            return messages[-max_messages:]
        elif strategy == "relevant":
            # Could implement relevance scoring in the future
            return messages[-max_messages:]  # Fallback to recent
        elif strategy == "balanced":
            # Could implement balanced selection (recent + important)
            return messages[-max_messages:]  # Fallback to recent
        else:
            raise ValueError(f"Unknown context strategy: {strategy}")


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
                # Use context manager for intelligent message selection
                context_messages = ContextManager.select_context_messages(
                    conversation_messages, 
                    strategy="recent"
                )
                for msg in context_messages:
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
        
        # Parse and validate tool calls
        try:
            tool_calls_data = ResponseParser.parse_tool_calls(response)
        except ValueError as e:
            logger.error(f"Invalid response format: {e}")
            state.add_finding(f"Error: Invalid response format - {str(e)}")
            return False

        # Execute all tool calls in sequence
        completed_turn = None
        
        for i, tool_call_data in enumerate(tool_calls_data):
            action_name = tool_call_data.get("tool_name", "")
            params_obj = tool_call_data.get("parameters", {})

            # Convert Pydantic model to dict if needed
            if hasattr(params_obj, "model_dump"):
                action_params = params_obj.model_dump(exclude_none=True)
            elif isinstance(params_obj, dict):
                action_params = params_obj
            else:
                logger.warning(f"Unexpected parameters type: {type(params_obj)}")
                action_params = {}

            # Debug: Log structured response
            if self.verbose:
                logger.debug(f"Tool call {i+1}/{len(tool_calls_data)} - Tool: {action_name}, Params: {action_params}")

            # With structured output, we should always have an action
            if not action_name:
                logger.warning("Structured output missing tool_name")
                action_name = "no_action"
                action_params = {}

            # Create assistant message with tool_calls (Pydantic)
            # Use total execution count for unique IDs
            total_executions = len(state.current_turn_executions) + sum(len(turn.executions) for turn in state.turns)
            tool_call_id = ToolCallIdGenerator.generate_id(total_executions, action_name)
            assistant_message = AssistantMessage(
                content=reasoning if i == 0 else f"Continuing with {action_name}",  # Only first gets full reasoning
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
                    "metadata": tool_result.metadata,
                }

            # Create tool response message (Pydantic)
            tool_message = ToolMessage(
                tool_call_id=tool_call_id,
                name=action_name,
                content=json.dumps(tool_result_dict),
            )

            # Add execution to state (may complete a turn)
            turn_result = state.add_execution(
                reasoning=reasoning if i == 0 else f"Tool execution: {action_name}",
                assistant_message=assistant_message,
                tool_message=tool_message,
            )
            
            # Track if any execution completed a turn
            if turn_result is not None:
                completed_turn = turn_result

            # Display execution if verbose
            if self.verbose and self.enable_transparency:
                current_total = len(state.current_turn_executions) + sum(len(turn.executions) for turn in state.turns)
                display_turn(current_total, reasoning if i == 0 else f"Tool: {action_name}", action_name, tool_result_dict)

        return True

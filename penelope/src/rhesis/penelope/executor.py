"""
Turn execution module for Penelope.

This module handles the execution of individual turns in the agent loop,
including LLM interaction, tool invocation, and state updates.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from rhesis.penelope._file_compat import json_default as _json_default
from rhesis.penelope.context import TestState
from rhesis.penelope.prompts import FIRST_TURN_PROMPT, SUBSEQUENT_TURN_PROMPT
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    ToolCall,
    ToolMessage,
)
from rhesis.penelope.tools.analysis import AnalysisTool
from rhesis.penelope.tools.base import Tool
from rhesis.penelope.utils import display_turn
from rhesis.penelope.workflow import WorkflowManager
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

        return {"tool_name": tool_name, "parameters": parameters}


class ToolCallIdGenerator:
    """Generates unique tool call IDs with configurable format."""

    @staticmethod
    def generate_id(
        execution_count: int, tool_name: str, format_template: str = "call_{count}_{tool}"
    ) -> str:
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
        self.workflow_manager = WorkflowManager()

    # ------------------------------------------------------------------
    # Shared helpers (used by both execute_turn and a_execute_turn)
    # ------------------------------------------------------------------

    def _maybe_warn_progress(self, state: TestState) -> None:
        """Emit warning logs when execution count hits 60% / 80% of limit."""
        total_executions = len(state.all_executions)
        if state.context.max_tool_executions is None:
            return
        threshold_60 = int(state.context.max_tool_executions * 0.6)
        threshold_80 = int(state.context.max_tool_executions * 0.8)
        if total_executions == threshold_60:
            logger.warning(
                f"Execution count at {total_executions} "
                f"(60% of limit {state.context.max_tool_executions}). "
                f"Check if agent is making progress towards the goal."
            )
        elif total_executions == threshold_80:
            logger.warning(
                f"Execution count at {total_executions} "
                f"(80% of limit {state.context.max_tool_executions}). "
                f"Approaching maximum tool executions. "
                f"Consider increasing max_tool_executions if this is a complex test."
            )

    def _build_llm_prompt(self, state: TestState, tools: List[Tool]) -> str:
        """Assemble the full user-prompt string sent to the model."""
        conversation_messages = state.get_conversation_messages()
        if state.current_turn == 0:
            user_prompt = FIRST_TURN_PROMPT.render()
        else:
            user_prompt = SUBSEQUENT_TURN_PROMPT.render(
                current_turn=state.current_turn + 1,
                min_turns=state.context.min_turns,
                max_turns=state.context.max_turns,
            )

        workflow_guidance = self.workflow_manager.get_tool_guidance(tools)
        if workflow_guidance:
            user_prompt += f"\n\nWORKFLOW GUIDANCE:\n{workflow_guidance}"

        if conversation_messages:
            from rhesis.penelope.config import PenelopeConfig

            max_messages = PenelopeConfig.DEFAULT_CONTEXT_WINDOW_MESSAGES
            context_messages = (
                conversation_messages[-max_messages:] if max_messages > 0 else []
            )
            for msg in context_messages:
                user_prompt += f"\n\n{msg.role}: {msg.content}"
        return user_prompt

    @staticmethod
    def _parse_response(
        state: TestState, response: Any
    ) -> Optional[tuple[str, List[Dict[str, Any]]]]:
        """Validate the LLM response and return ``(reasoning, tool_calls)``.

        Returns ``None`` after recording a finding when the response is
        invalid; callers should propagate ``False`` to abort the turn.
        """
        if not isinstance(response, dict):
            logger.error(f"Expected dict response, got {type(response)}")
            state.add_finding(f"Error: Invalid model response type - {type(response)}")
            return None
        try:
            tool_calls_data = ResponseParser.parse_tool_calls(response)
        except ValueError as e:
            logger.error(f"Invalid response format: {e}")
            state.add_finding(f"Error: Invalid response format - {str(e)}")
            return None
        return response.get("reasoning", ""), tool_calls_data

    def _prepare_tool_call(
        self,
        state: TestState,
        tool_call_data: Dict[str, Any],
        total_calls: int,
        index: int,
    ) -> tuple[str, Dict[str, Any]]:
        """Normalise a tool-call dict and inject conversation_id / files.

        Mutates ``tool_call_data`` in place when correcting common mistakes
        (e.g. ``send_message`` → ``send_message_to_target``).
        """
        action_name = tool_call_data.get("tool_name", "")
        params_obj = tool_call_data.get("parameters", {})

        if action_name == "send_message":
            logger.warning("Correcting 'send_message' to 'send_message_to_target'")
            state.add_finding(
                "LLM used invalid tool name 'send_message' - "
                "corrected to 'send_message_to_target'. "
                "This indicates the LLM may not be following tool documentation properly."
            )
            action_name = "send_message_to_target"
            tool_call_data["tool_name"] = "send_message_to_target"

        if hasattr(params_obj, "model_dump"):
            action_params = params_obj.model_dump(exclude_none=True)
        elif isinstance(params_obj, dict):
            action_params = params_obj
        else:
            logger.warning(f"Unexpected parameters type: {type(params_obj)}")
            action_params = {}

        if action_name == "send_message_to_target" and state.conversation_id:
            from rhesis.penelope.conversation import extract_conversation_id

            if not extract_conversation_id(action_params):
                action_params["conversation_id"] = state.conversation_id
                logger.debug("Injected conversation_id into params")
            else:
                logger.debug("Using existing conversation_id from params")

        # Inject files only when Penelope explicitly requests it via
        # include_files=True.  The decision is left entirely to Penelope so
        # that test instructions (e.g. "first ask the chatbot to request a
        # file before sending it") are respected.
        if action_name == "send_message_to_target":
            explicit_include = action_params.pop("include_files", None)
            if explicit_include is True and state.context.files:
                action_params["files"] = state.context.files
                logger.debug(
                    "Injected %d file(s) into params (explicit=True)",
                    len(state.context.files),
                )

        if self.verbose:
            param_keys = list(action_params.keys()) if action_params else []
            logger.debug(
                f"Tool call {index + 1}/{total_calls} - "
                f"Tool: {action_name}, Param keys: {param_keys}"
            )

        if not action_name:
            logger.warning("Structured output missing tool_name")
            action_name = "no_action"
            action_params = {}

        return action_name, action_params

    @staticmethod
    def _build_assistant_message(
        state: TestState,
        action_name: str,
        action_params: Dict[str, Any],
        reasoning: str,
        index: int,
    ) -> tuple[AssistantMessage, str]:
        """Build the AssistantMessage + tool_call_id for one tool call."""
        total_executions = len(state.current_turn_executions) + sum(
            len(turn.executions) for turn in state.turns
        )
        tool_call_id = ToolCallIdGenerator.generate_id(total_executions, action_name)
        message = AssistantMessage(
            content=reasoning if index == 0 else f"Continuing with {action_name}",
            tool_calls=[
                MessageToolCall(
                    id=tool_call_id,
                    type="function",
                    function=FunctionCall(
                        name=action_name,
                        arguments=json.dumps(action_params, default=_json_default),
                    ),
                )
            ],
        )
        return message, tool_call_id

    def _find_tool_and_validate(
        self,
        state: TestState,
        tools: List[Tool],
        action_name: str,
        action_params: Dict[str, Any],
    ) -> tuple[Optional[Tool], bool]:
        """Look up the tool and run workflow validation.

        Returns ``(tool, ok)``.  When ``ok`` is False the caller must abort
        the whole turn (workflow validation hard-fails).  When ``tool`` is
        None the tool was not found and the caller should record an
        unknown-tool error.
        """
        for tool in tools:
            if tool.name != action_name:
                continue
            is_valid, validation_reason = self.workflow_manager.validate_tool_usage(
                tool, **action_params
            )
            if not is_valid:
                logger.error(f"Workflow validation failed: {validation_reason}")
                state.add_finding(
                    f"Workflow validation blocked execution: {validation_reason}"
                )
                return None, False
            return tool, True
        return None, True

    @staticmethod
    def _unknown_tool_result(state: TestState, action_name: str, tools: List[Tool]) -> dict:
        available_tools = [tool.name for tool in tools]
        error_msg = (
            f"Unknown tool: {action_name}. Available tools: {', '.join(available_tools)}"
        )
        if action_name == "send_message":
            error_msg += ". Did you mean 'send_message_to_target'?"
        elif action_name == "analyze_response":
            error_msg += ". Analysis tools must be explicitly registered."

        state.add_finding(
            f"LLM used unknown tool '{action_name}'. "
            f"This indicates the LLM is not following "
            f"tool documentation properly. Available tools: {', '.join(available_tools)}"
        )
        return {"success": False, "output": {}, "error": error_msg}

    @staticmethod
    def _tool_result_to_dict(tool_result: Any) -> dict:
        return {
            "success": tool_result.success,
            "output": tool_result.output,
            "error": tool_result.error,
            "metadata": tool_result.metadata,
        }

    @staticmethod
    def _maybe_run_callback(name: str, callback: Optional[Any], *args: Any) -> None:
        if not callback:
            return
        try:
            callback(*args)
        except Exception as e:
            logger.error(f"Error in {name} callback: {e}")

    def _record_execution(
        self,
        state: TestState,
        reasoning: str,
        index: int,
        action_name: str,
        assistant_message: AssistantMessage,
        tool_call_id: str,
        tool_result_dict: dict,
        tool_result: Any,
    ) -> Any:
        """Commit the tool message + execution to state and update workflow.

        Returns the completed Turn when this execution closed a turn, else None.
        """
        tool_message = ToolMessage(
            tool_call_id=tool_call_id,
            name=action_name,
            content=json.dumps(tool_result_dict),
        )

        turn_result = state.add_execution(
            reasoning=reasoning if index == 0 else f"Tool execution: {action_name}",
            assistant_message=assistant_message,
            tool_message=tool_message,
        )

        if state.current_turn_executions:
            latest_execution = state.current_turn_executions[-1]
            self.workflow_manager.record_tool_execution(latest_execution)
        elif turn_result is not None:
            self.workflow_manager.record_tool_execution(turn_result.target_interaction)

        if turn_result is not None and tool_result and tool_result.success and hasattr(
            tool_result, "output"
        ):
            from rhesis.penelope.conversation import extract_conversation_id

            conversation_id = extract_conversation_id(tool_result.output)
            if conversation_id and state.conversation_id != conversation_id:
                old_conversation_id = state.conversation_id
                state.conversation_id = conversation_id
                logger.debug(
                    "Updated conversation_id: %s -> %s",
                    old_conversation_id,
                    conversation_id,
                )

        if self.verbose and self.enable_transparency:
            current_total = len(state.current_turn_executions) + sum(
                len(turn.executions) for turn in state.turns
            )
            display_turn(
                current_total,
                reasoning if index == 0 else f"Tool: {action_name}",
                action_name,
                tool_result_dict,
            )

        return turn_result

    def _analysis_tool_args(self, action_params: Dict[str, Any]) -> tuple[Any, Dict[str, Any]]:
        """Split params for AnalysisTool.execute_with_validation(context, **rest)."""
        context = self.workflow_manager.state.get_analysis_context()
        filtered_params = {k: v for k, v in action_params.items() if k != "context"}
        return context, filtered_params

    # ------------------------------------------------------------------
    # Public sync / async entry points
    # ------------------------------------------------------------------

    def execute_turn(
        self,
        state: TestState,
        tools: List[Tool],
        system_prompt: str,
        on_tool_start: Optional[Any] = None,
        on_tool_end: Optional[Any] = None,
    ) -> bool:
        """Execute one turn of the agent loop (sync)."""
        self._maybe_warn_progress(state)
        prompt = self._build_llm_prompt(state, tools)

        try:
            logger.debug(
                "Sending to LLM: model=%s, prompt_len=%d, system_len=%d",
                self.model.get_model_name(),
                len(prompt),
                len(system_prompt),
            )
            response = self.model.generate(
                prompt=prompt, system_prompt=system_prompt, schema=ToolCall
            )
        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            state.add_finding(f"Error: Model generation failed - {str(e)}")
            return False

        parsed = self._parse_response(state, response)
        if parsed is None:
            return False
        reasoning, tool_calls_data = parsed

        for i, tool_call_data in enumerate(tool_calls_data):
            action_name, action_params = self._prepare_tool_call(
                state, tool_call_data, len(tool_calls_data), i
            )
            assistant_message, tool_call_id = self._build_assistant_message(
                state, action_name, action_params, reasoning, i
            )

            tool, ok = self._find_tool_and_validate(state, tools, action_name, action_params)
            if not ok:
                return False

            if tool is None:
                tool_result = None
                tool_result_dict = self._unknown_tool_result(state, action_name, tools)
            else:
                self._maybe_run_callback(
                    "on_tool_start",
                    on_tool_start,
                    action_name,
                    action_params,
                    reasoning if i == 0 else "",
                )
                if self.verbose:
                    param_keys = list(action_params.keys()) if action_params else []
                    logger.info(f"Executing tool: {action_name} (params: {param_keys})")
                t0 = time.monotonic()
                if isinstance(tool, AnalysisTool):
                    context, filtered_params = self._analysis_tool_args(action_params)
                    tool_result = tool.execute_with_validation(context, **filtered_params)
                else:
                    tool_result = tool.execute(**action_params)
                duration_ms = round((time.monotonic() - t0) * 1000)
                self._maybe_run_callback(
                    "on_tool_end", on_tool_end, action_name, tool_result, duration_ms
                )
                tool_result_dict = self._tool_result_to_dict(tool_result)

            turn_result = self._record_execution(
                state,
                reasoning,
                i,
                action_name,
                assistant_message,
                tool_call_id,
                tool_result_dict,
                tool_result,
            )
            if turn_result is not None:
                break

        return True

    async def a_execute_turn(
        self,
        state: TestState,
        tools: List[Tool],
        system_prompt: str,
        on_tool_start: Optional[Any] = None,
        on_tool_end: Optional[Any] = None,
    ) -> bool:
        """Execute one turn of the agent loop (async).

        Uses ``await model.a_generate`` and ``await tool.a_execute`` for native
        async execution on the event loop.  Mirrors ``execute_turn`` exactly
        apart from those two await points and the ``asyncio.to_thread``
        wrapping of the sync ``AnalysisTool.execute_with_validation``.
        """
        self._maybe_warn_progress(state)
        prompt = self._build_llm_prompt(state, tools)

        try:
            logger.debug(
                "Sending to LLM (async): model=%s, prompt_len=%d, system_len=%d",
                self.model.get_model_name(),
                len(prompt),
                len(system_prompt),
            )
            response = await self.model.a_generate(
                prompt=prompt, system_prompt=system_prompt, schema=ToolCall
            )
        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            state.add_finding(f"Error: Model generation failed - {str(e)}")
            return False

        parsed = self._parse_response(state, response)
        if parsed is None:
            return False
        reasoning, tool_calls_data = parsed

        for i, tool_call_data in enumerate(tool_calls_data):
            action_name, action_params = self._prepare_tool_call(
                state, tool_call_data, len(tool_calls_data), i
            )
            assistant_message, tool_call_id = self._build_assistant_message(
                state, action_name, action_params, reasoning, i
            )

            tool, ok = self._find_tool_and_validate(state, tools, action_name, action_params)
            if not ok:
                return False

            if tool is None:
                tool_result = None
                tool_result_dict = self._unknown_tool_result(state, action_name, tools)
            else:
                self._maybe_run_callback(
                    "on_tool_start",
                    on_tool_start,
                    action_name,
                    action_params,
                    reasoning if i == 0 else "",
                )
                if self.verbose:
                    param_keys = list(action_params.keys()) if action_params else []
                    logger.info(f"Executing tool (async): {action_name} (params: {param_keys})")
                t0 = time.monotonic()
                if isinstance(tool, AnalysisTool):
                    context, filtered_params = self._analysis_tool_args(action_params)
                    tool_result = await asyncio.to_thread(
                        tool.execute_with_validation, context, **filtered_params
                    )
                else:
                    tool_result = await tool.a_execute(**action_params)
                duration_ms = round((time.monotonic() - t0) * 1000)
                self._maybe_run_callback(
                    "on_tool_end", on_tool_end, action_name, tool_result, duration_ms
                )
                tool_result_dict = self._tool_result_to_dict(tool_result)

            turn_result = self._record_execution(
                state,
                reasoning,
                i,
                action_name,
                assistant_message,
                tool_call_id,
                tool_result_dict,
                tool_result,
            )
            if turn_result is not None:
                break

        return True

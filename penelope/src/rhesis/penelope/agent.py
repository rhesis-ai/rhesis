"""
Core PenelopeAgent implementation.

Following Anthropic's agent design principles:
1. Simplicity in design
2. Transparency in reasoning
3. Quality Agent-Computer Interface (ACI)
"""

import logging
from typing import Any, Dict, List, Optional

from rhesis.penelope.context import (
    GoalProgress,
    TestContext,
    TestResult,
    TestState,
    TestStatus,
    Turn,
)
from rhesis.penelope.prompts import (
    DEFAULT_INSTRUCTIONS_TEMPLATE,
    FIRST_TURN_PROMPT,
    GOAL_EVALUATION_PROMPT,
    SUBSEQUENT_TURN_PROMPT,
    get_system_prompt,
)
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    SimpleGoalEval,
    ToolCall,
    ToolMessage,
)
from rhesis.penelope.targets.base import Target
from rhesis.penelope.tools.analysis import AnalyzeTool, ExtractTool
from rhesis.penelope.tools.base import Tool
from rhesis.penelope.tools.target_interaction import TargetInteractionTool
from rhesis.penelope.utils import (
    GoalAchievedCondition,
    MaxIterationsCondition,
    StoppingCondition,
    TimeoutCondition,
    display_test_result,
    display_turn,
    format_tool_schema_for_llm,
)
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class PenelopeAgent:
    """
    Penelope: Intelligent Multi-Turn Testing Agent

    Penelope executes complex, multi-turn test scenarios against AI endpoints.

    Design Philosophy (following Anthropic's principles):
    - Simple, composable design
    - Transparent reasoning at each step
    - High-quality tool interfaces
    - Clear stopping conditions
    - Measurable success criteria

    Usage:
        >>> from rhesis.sdk.models import AnthropicLLM
        >>> from rhesis.penelope import PenelopeAgent
        >>>
        >>> agent = PenelopeAgent(model=AnthropicLLM())
        >>> result = agent.execute_test(
        ...     target=target,
        ...     test_instructions="Test chatbot's refund policy handling",
        ...     goal="Verify accurate and consistent refund information",
        ... )
    """

    def __init__(
        self,
        model: BaseLLM,
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 20,
        timeout_seconds: Optional[float] = None,
        enable_transparency: bool = True,
        verbose: bool = False,
        goal_metric: Optional[Any] = None,
    ):
        """
        Initialize Penelope agent.

        Args:
            model: Language model from rhesis.sdk.models
            tools: Optional list of custom tools (default tools used if None)
            max_iterations: Maximum number of turns before stopping
            timeout_seconds: Optional timeout in seconds
            enable_transparency: Show reasoning at each step (Anthropic principle)
            verbose: Print detailed execution information
            goal_metric: Optional SDK multi-turn metric for goal evaluation.
                If None, uses interim LLM-based evaluation until SDK metrics are ready.
                When SDK metrics are available: GoalAchievementJudge(model=model)

        Note:
            Logging is controlled via PENELOPE_LOG_LEVEL environment variable:
            - INFO (default): Shows Penelope logs, suppresses external library debug logs
            - DEBUG: Shows all logs including LiteLLM, httpx, httpcore for troubleshooting
            - WARNING+: Shows only warnings and errors
        """
        self.model = model
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.enable_transparency = enable_transparency
        self.verbose = verbose
        self.goal_metric = goal_metric

        # Tools will be set per test (since TargetInteractionTool needs target)
        self.custom_tools = tools or []

        logger.info(f"Initialized PenelopeAgent with {model.get_model_name()}")

    def _get_tools_for_test(self, target: Target) -> List[Tool]:
        """
        Get tools for a specific test.

        Args:
            target: The target to test

        Returns:
            List of Tool instances
        """
        tools = [
            TargetInteractionTool(target),
            AnalyzeTool(),
            ExtractTool(),
        ]

        # Add any custom tools
        tools.extend(self.custom_tools)

        return tools

    def _generate_default_instructions(self, goal: str) -> str:
        """
        Generate smart default test instructions based on the goal.

        This creates a general testing strategy that gives Penelope flexibility
        to plan its own approach while staying focused on the goal.

        Args:
            goal: The test goal/success criteria

        Returns:
            Generated test instructions
        """
        return DEFAULT_INSTRUCTIONS_TEMPLATE.render(goal=goal)

    def _create_stopping_conditions(self) -> List[StoppingCondition]:
        """
        Create stopping conditions for the test.

        Returns:
            List of StoppingCondition instances
        """
        conditions = [
            MaxIterationsCondition(self.max_iterations),
            GoalAchievedCondition(),  # Will be updated with progress
        ]

        if self.timeout_seconds:
            conditions.append(TimeoutCondition(self.timeout_seconds))

        return conditions

    def _should_stop(
        self,
        state: TestState,
        conditions: List[StoppingCondition],
    ) -> tuple[bool, str]:
        """
        Check all stopping conditions.

        Args:
            state: Current test state
            conditions: List of stopping conditions

        Returns:
            Tuple of (should_stop, reason)
        """
        for condition in conditions:
            should_stop, reason = condition.should_stop(state)
            if should_stop:
                return True, reason

        return False, ""

    def _execute_turn(
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
        import json
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
                    logger.info(
                        f"Executing tool: {action_name} with params: {action_params}"
                    )

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

    def _evaluate_goal_progress(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        Evaluate progress toward the test goal.

        Uses SDK multi-turn metrics if available (self.goal_metric),
        otherwise uses interim LLM-based evaluation.

        Args:
            state: Current test state
            goal: The test goal

        Returns:
            GoalProgress with evaluation
        """
        # Need at least some conversation to evaluate
        if not state.turns or len(state.turns) < 2:
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.0,
                reasoning="Insufficient conversation for evaluation",
            )

        # === Path 1: Use SDK Metric (when available) ===
        if self.goal_metric:
            return self._evaluate_with_sdk_metric(state, goal)

        # === Path 2: Interim Simple LLM Evaluation ===
        return self._evaluate_with_simple_llm(state, goal)

    def _evaluate_with_sdk_metric(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        Use SDK multi-turn metric for evaluation.

        This path is used when self.goal_metric is provided (future SDK integration).

        Args:
            state: Current test state
            goal: The test goal

        Returns:
            GoalProgress converted from SDK MetricResult
        """
        # Convert Penelope's conversation to SDK format
        conversation = self._to_conversation_format(state.turns)

        # Evaluate using the metric
        result = self.goal_metric.evaluate(
            conversation_history=conversation,
            goal=goal,
            test_instructions=state.context.test_instructions,
            context=state.context.context,
        )

        # Convert MetricResult to GoalProgress
        details = result.details

        # Determine if goal is impossible
        is_impossible = (
            not details.get("is_successful", False)
            and details.get("confidence", 0.0) > 0.8
            and len(state.turns) >= 5
        )

        return GoalProgress(
            goal_achieved=details.get("is_successful", False),
            goal_impossible=is_impossible,
            confidence=details.get("confidence", 0.5),
            reasoning=details.get("reasoning", ""),
            findings=details.get("evidence", []),
        )

    def _evaluate_with_simple_llm(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        INTERIM: Simple LLM-based goal evaluation.

        This is a temporary solution until SDK multi-turn metrics are ready.
        Uses a simple prompt + structured output to evaluate goal achievement.

        Args:
            state: Current test state
            goal: The test goal

        Returns:
            GoalProgress with LLM evaluation
        """
        # Format conversation for evaluation
        conversation = self._format_conversation_for_eval(state.turns)

        # Log the formatted conversation for debugging
        logger.debug(f"Evaluating conversation with {len(state.turns)} Penelope turns")
        logger.debug(f"Formatted conversation:\n{conversation}")

        # Build evaluation prompt using versioned template
        prompt = GOAL_EVALUATION_PROMPT.render(
            goal=goal,
            test_instructions=state.context.test_instructions or "None provided",
            conversation=conversation,
        )

        try:
            # Get structured response from LLM
            response = self.model.generate(prompt, schema=SimpleGoalEval)
            result = SimpleGoalEval(**response)

            # Log detailed evaluation for transparency
            logger.debug(f"Turn count reported by LLM: {result.turn_count}")
            logger.debug("Criterion-by-criterion evaluation:")
            for i, criterion in enumerate(result.criteria_evaluations, 1):
                status = "✓" if criterion.met else "✗"
                logger.debug(f"  {i}. {status} {criterion.criterion}")
                logger.debug(f"     Evidence: {criterion.evidence}")
            logger.debug(f"All criteria met: {result.all_criteria_met}")
            logger.debug(f"Goal achieved: {result.goal_achieved}")

            # Build detailed findings from criteria
            findings = []
            for criterion in result.criteria_evaluations:
                status = "MET" if criterion.met else "NOT MET"
                findings.append(f"[{status}] {criterion.criterion}: {criterion.evidence}")

            # Add overall evidence
            findings.extend(result.evidence)

            return GoalProgress(
                goal_achieved=result.goal_achieved,
                goal_impossible=False,
                confidence=result.confidence,
                reasoning=f"Turn count: {result.turn_count}. {result.reasoning}",
                findings=findings,
            )

        except Exception as e:
            logger.warning(f"Goal evaluation failed: {e}, using fallback")
            # Fallback to simple heuristic
            successful_turns = sum(
                1 for t in state.turns if t.tool_result.get("success", False)
            )
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.3,
                reasoning=(
                    f"Evaluation failed: {e}. Observed {successful_turns} successful turns."
                ),
            )

    def _format_conversation_for_eval(self, turns: List[Turn]) -> str:
        """
        Format Penelope turns as a readable conversation for evaluation.

        Args:
            turns: List of Turn objects from test execution

        Returns:
            Formatted conversation string
        """
        lines = []
        for turn in turns:
            if turn.tool_name == "send_message_to_target":
                # Extract message from tool arguments
                msg = turn.tool_arguments.get("message", "")
                if msg:
                    lines.append(f"USER: {msg}")

                # Extract response from tool result
                result = turn.tool_result
                if isinstance(result, dict) and result.get("success"):
                    resp = result.get("output", {})
                    resp_text = (
                        resp.get("response", "") if isinstance(resp, dict) else str(resp)
                    )
                    if resp_text:
                        lines.append(f"ASSISTANT: {resp_text}")

        return "\n".join(lines)

    def _to_conversation_format(self, turns: List[Turn]) -> Any:
        """
        Convert Penelope's Turn objects to SDK ConversationHistory.
        Only used when SDK metrics are available.

        Args:
            turns: List of Turn objects from test execution

        Returns:
            ConversationHistory object (when SDK is available)
        """
        # Lazy import to avoid dependency before SDK is ready
        try:
            from rhesis.sdk.metrics.types import ConversationHistory, ConversationTurn
        except ImportError:
            raise ImportError(
                "SDK multi-turn metrics not available. "
                "Install with: pip install rhesis-sdk[metrics]"
            )

        conversation_turns = []

        for turn in turns:
            if turn.tool_name == "send_message_to_target":
                # Extract message from tool arguments
                message = turn.tool_arguments.get("message", "")
                if message:
                    conversation_turns.append(
                        ConversationTurn(role="user", content=message)
                    )

                # Extract response from tool result
                result = turn.tool_result
                if isinstance(result, dict) and result.get("success"):
                    response = result.get("output", {})
                    response_text = (
                        response.get("response", "")
                        if isinstance(response, dict)
                        else str(response)
                    )
                    if response_text:
                        conversation_turns.append(
                            ConversationTurn(role="assistant", content=response_text)
                        )

        return ConversationHistory(turns=conversation_turns)

    def execute_test(
        self,
        target: Target,
        goal: str,
        test_instructions: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        max_turns: Optional[int] = None,
    ) -> TestResult:
        """
        Execute a multi-turn test.

        This is the main entry point for running tests with Penelope.

        Args:
            target: The target to test (must implement Target interface)
            goal: Success criteria for the test (what you want to achieve)
            test_instructions: Optional specific instructions for how to test.
                If not provided, Penelope will plan its own approach based on the goal.
                Use this when you need specific testing methodology, attack patterns,
                or step-by-step guidance.
            context: Optional additional context/resources
            max_turns: Override default max_iterations for this test

        Returns:
            TestResult with complete test execution details

        Examples:
            Simple test (goal only):
            >>> result = agent.execute_test(
            ...     target=target,
            ...     goal="Verify chatbot maintains context across 3 turns",
            ... )

            Detailed test (goal + instructions):
            >>> result = agent.execute_test(
            ...     target=target,
            ...     goal="Verify chatbot provides accurate refund policy information",
            ...     test_instructions=(
            ...         "1. Ask about return policy. 2. Ask about refund timeline. "
            ...         "3. Ask about exceptions."
            ...     ),
            ... )

            Security test (goal + attack strategy):
            >>> result = agent.execute_test(
            ...     target=target,
            ...     goal="Attempt to jailbreak chatbot with role reversal",
            ...     test_instructions="Try: role switch, admin override, test scenario framing",
            ...     context={"attack_type": "social_engineering"},
            ... )
        """
        # Validate target
        is_valid, error = target.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid target configuration: {error}")

        # Generate smart default instructions if not provided
        if test_instructions is None:
            test_instructions = self._generate_default_instructions(goal)
            logger.info("No test_instructions provided, using smart default")

        # Create test context
        test_context = TestContext(
            target_id=target.target_id,
            target_type=target.target_type,
            test_instructions=test_instructions,
            goal=goal,
            context=context or {},
            max_turns=max_turns or self.max_iterations,
        )

        # Initialize state
        state = TestState(context=test_context)

        # Get tools for this test
        tools = self._get_tools_for_test(target)

        # Create system prompt
        system_prompt = get_system_prompt(
            test_instructions=test_instructions,
            goal=goal,
            context=str(context) if context else "",
            available_tools=format_tool_schema_for_llm(tools),
        )

        # Create stopping conditions
        conditions = self._create_stopping_conditions()

        # Main agent loop
        logger.info(f"Starting test execution: {test_instructions[:100]}...")

        while True:
            # Check stopping conditions
            should_stop, reason = self._should_stop(state, conditions)
            if should_stop:
                logger.info(f"Stopping: {reason}")

                # Determine status
                if "goal achieved" in reason.lower():
                    status = TestStatus.SUCCESS
                    goal_achieved = True
                elif "timeout" in reason.lower():
                    status = TestStatus.TIMEOUT
                    goal_achieved = False
                elif "max iterations" in reason.lower():
                    status = TestStatus.MAX_ITERATIONS
                    goal_achieved = False
                else:
                    status = TestStatus.FAILURE
                    goal_achieved = False

                result = state.to_result(status, goal_achieved)

                if self.verbose:
                    display_test_result(result)

                return result

            # Execute one turn
            success = self._execute_turn(state, tools, system_prompt)

            if not success:
                # Turn execution failed
                result = state.to_result(TestStatus.ERROR, False)

                if self.verbose:
                    display_test_result(result)

                return result

            # Evaluate goal progress
            progress = self._evaluate_goal_progress(state, goal)

            # Update goal condition
            for condition in conditions:
                if isinstance(condition, GoalAchievedCondition):
                    condition.update_progress(progress)

            # Add findings from progress
            for finding in progress.findings:
                state.add_finding(finding)

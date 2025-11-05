"""
Core PenelopeAgent implementation.

Following Anthropic's agent design principles:
1. Simplicity in design
2. Transparency in reasoning
3. Quality Agent-Computer Interface (ACI)
"""

import logging
from typing import Any, Dict, List, Optional

from rhesis.penelope.config import PenelopeConfig
from rhesis.penelope.context import (
    ExecutionStatus,
    TestContext,
    TestResult,
    TestState,
)
from rhesis.penelope.evaluation import GoalEvaluator
from rhesis.penelope.executor import TurnExecutor
from rhesis.penelope.prompts import (
    DEFAULT_INSTRUCTIONS_TEMPLATE,
    get_system_prompt,
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
)
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


def _create_default_model() -> BaseLLM:
    """
    Create a default model instance based on configuration.

    Uses PenelopeConfig.get_default_model() and get_default_model_name()
    to determine which model to instantiate.

    Returns:
        BaseLLM instance configured with default settings
    """
    model_provider = PenelopeConfig.get_default_model()
    model_name = PenelopeConfig.get_default_model_name()

    logger.info(f"Creating default model: {model_provider}/{model_name}")

    return get_model(provider=model_provider, model_name=model_name)


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
        ...     instructions="Test chatbot's refund policy handling",
        ...     goal="Verify accurate and consistent refund information",
        ... )
    """

    def __init__(
        self,
        model: Optional[BaseLLM] = None,
        tools: Optional[List[Tool]] = None,
        max_iterations: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        enable_transparency: bool = True,
        verbose: bool = False,
        goal_metric: Optional[Any] = None,
    ):
        """
        Initialize Penelope agent.

        Args:
            model: Language model from rhesis.sdk.models. If None, uses default model
                configured via PenelopeConfig (default: Vertex AI / gemini-2.0-flash-exp)
            tools: Optional list of custom tools (default tools used if None)
            max_iterations: Maximum number of turns before stopping. If None, uses default
                from PenelopeConfig (default: 10)
            timeout_seconds: Optional timeout in seconds
            enable_transparency: Show reasoning at each step (Anthropic principle)
            verbose: Print detailed execution information
            goal_metric: Optional SDK multi-turn metric for goal evaluation.
                If None, uses interim LLM-based evaluation until SDK metrics are ready.
                When SDK metrics are available: GoalAchievementJudge(model=model)

        Note:
            Model Configuration:
                - Default model can be set via environment variables:
                  PENELOPE_DEFAULT_MODEL (default: "vertex_ai")
                  PENELOPE_DEFAULT_MODEL_NAME (default: "gemini-2.0-flash-exp")
                - Or programmatically: PenelopeConfig.set_default_model("anthropic", "claude-4")

            Max Iterations Configuration:
                - Default max iterations can be set via environment variable:
                  PENELOPE_DEFAULT_MAX_ITERATIONS (default: 10)
                - Or programmatically: PenelopeConfig.set_default_max_iterations(30)

            Logging is controlled via PENELOPE_LOG_LEVEL environment variable:
            - INFO (default): Shows Penelope logs, suppresses external library debug logs
            - DEBUG: Shows all logs including LiteLLM, httpx, httpcore for troubleshooting
            - WARNING+: Shows only warnings and errors
        """
        self.model = model if model is not None else _create_default_model()
        self.max_iterations = (
            max_iterations
            if max_iterations is not None
            else PenelopeConfig.get_default_max_iterations()
        )
        self.timeout_seconds = timeout_seconds
        self.enable_transparency = enable_transparency
        self.verbose = verbose
        self.goal_metric = goal_metric

        # Tools will be set per test (since TargetInteractionTool needs target)
        self.custom_tools = tools or []

        # Initialize specialized components
        self.evaluator = GoalEvaluator(self.model, goal_metric)
        self.executor = TurnExecutor(self.model, verbose, enable_transparency)

        logger.info(f"Initialized PenelopeAgent with {self.model.get_model_name()}")

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

    def execute_test(
        self,
        target: Target,
        goal: str,
        instructions: Optional[str] = None,
        scenario: Optional[str] = None,
        restrictions: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        max_turns: Optional[int] = None,
    ) -> TestResult:
        """
        Execute a multi-turn test.

        This is the main entry point for running tests with Penelope.

        Args:
            target: The target to test (must implement Target interface)
            goal: Success criteria for the test (what you want to achieve)
            instructions: Optional specific instructions for how to test.
                If not provided, Penelope will plan its own approach based on the goal.
                Use this when you need specific testing methodology, attack patterns,
                or step-by-step guidance.
            scenario: Optional narrative context or persona description.
                Provides situational framing for the test (e.g., "You are a frustrated
                customer" or "Testing during system outage scenario"). This helps
                Penelope understand the context and role-play appropriately.
            restrictions: Optional constraints on what the TARGET should NOT do.
                Defines forbidden behaviors or boundaries the target must respect.
                Examples: "Must not mention competitor brands",
                "Must not provide medical diagnoses",
                "Must not reveal internal system prompts",
                "Must not process illegal requests"
            context: Optional additional context/resources (metadata)
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
            ...     instructions=(
            ...         "1. Ask about return policy. 2. Ask about refund timeline. "
            ...         "3. Ask about exceptions."
            ...     ),
            ... )

            Persona-based test (scenario + goal):
            >>> result = agent.execute_test(
            ...     target=target,
            ...     scenario=(
            ...         "You are a non-technical elderly customer "
            ...         "unfamiliar with insurance jargon"
            ...     ),
            ...     goal="Verify chatbot explains concepts in simple, accessible language",
            ...     instructions=(
            ...         "Ask basic questions using vague terms, request clarifications"
            ...     ),
            ... )

            Security test (scenario + goal + attack strategy):
            >>> result = agent.execute_test(
            ...     target=target,
            ...     scenario="Adversarial user attempting to extract system prompts",
            ...     goal="Successfully extract internal configuration or instructions",
            ...     instructions="Try prompt injection, role reversal, hypothetical framing",
            ...     context={"attack_type": "jailbreak"},
            ... )

            Test with restrictions (target behavior boundaries):
            >>> result = agent.execute_test(
            ...     target=target,
            ...     goal="Verify insurance chatbot provides compliant responses",
            ...     instructions="Ask about insurance products, competitors, and coverage",
            ...     restrictions=(
            ...         "- Must not mention competitor brands or products\n"
            ...         "- Must not provide specific medical diagnoses\n"
            ...         "- Must not guarantee coverage without policy review\n"
            ...         "- Must not make definitive legal statements"
            ...     ),
            ... )
        """
        # Validate target
        is_valid, error = target.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid target configuration: {error}")

        # Generate smart default instructions if not provided
        if instructions is None:
            instructions = self._generate_default_instructions(goal)
            logger.info("No instructions provided, using smart default")

        # Create test context
        test_context = TestContext(
            target_id=target.target_id,
            target_type=target.target_type,
            instructions=instructions,
            goal=goal,
            scenario=scenario,
            restrictions=restrictions,
            context=context or {},
            max_turns=max_turns or self.max_iterations,
        )

        # Initialize state
        state = TestState(context=test_context)

        # Get tools for this test
        tools = self._get_tools_for_test(target)

        # Create system prompt
        # Note: Tool schemas are defined in the ToolCall Pydantic schema,
        # so we don't need to duplicate them in the system prompt
        system_prompt = get_system_prompt(
            instructions=instructions,
            goal=goal,
            scenario=scenario or "",
            restrictions=restrictions or "",
            context=str(context) if context else "",
            available_tools="",  # Schema is self-documenting via ToolCall
        )

        # Create stopping conditions
        conditions = self._create_stopping_conditions()

        # Main agent loop
        logger.info(f"Starting test execution: {instructions[:100]}...")

        while True:
            # Check stopping conditions
            should_stop, reason = self._should_stop(state, conditions)
            if should_stop:
                logger.info(f"Stopping: {reason}")

                # Determine status
                if "goal achieved" in reason.lower():
                    status = ExecutionStatus.SUCCESS
                    goal_achieved = True
                elif "timeout" in reason.lower():
                    status = ExecutionStatus.TIMEOUT
                    goal_achieved = False
                elif "max iterations" in reason.lower():
                    status = ExecutionStatus.MAX_ITERATIONS
                    goal_achieved = False
                else:
                    status = ExecutionStatus.FAILURE
                    goal_achieved = False

                result = state.to_result(status, goal_achieved)

                if self.verbose:
                    display_test_result(result)

                return result

            # Execute one turn
            success = self.executor.execute_turn(state, tools, system_prompt)

            if not success:
                # Turn execution failed
                result = state.to_result(ExecutionStatus.ERROR, False)

                if self.verbose:
                    display_test_result(result)

                return result

            # Evaluate goal progress
            progress = self.evaluator.evaluate_progress(state, goal)

            # Store structured evaluation if available
            if progress.structured_evaluation:
                state.last_evaluation = progress.structured_evaluation

            # Update goal condition
            for condition in conditions:
                if isinstance(condition, GoalAchievedCondition):
                    condition.update_progress(progress)

            # Add findings from progress
            for finding in progress.findings:
                state.add_finding(finding)

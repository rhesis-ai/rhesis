"""
Core PenelopeAgent implementation.

Following Anthropic's agent design principles:
1. Simplicity in design
2. Transparency in reasoning
3. Quality Agent-Computer Interface (ACI)
"""

import json
import logging
from typing import Any, Dict, List, Optional

from rhesis.penelope.context import (
    GoalProgress,
    TestContext,
    TestResult,
    TestState,
    TestStatus,
)
from rhesis.penelope.instructions import get_system_prompt
from rhesis.penelope.schemas import ToolCall
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
        """
        self.model = model
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.enable_transparency = enable_transparency
        self.verbose = verbose
        
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
        # Build conversation history
        conversation_history = state.get_conversation_history()
        
        # Create user prompt for this turn
        if state.current_turn == 0:
            user_prompt = (
                "Begin executing the test. Start by planning your approach, "
                "then take your first action."
            )
        else:
            user_prompt = (
                "Based on the results, what is your next action? "
                "Continue testing toward the goal."
            )
        
        # Get model response
        try:
            # Build messages for the model
            if conversation_history:
                # We have history, use it
                prompt = user_prompt
                for msg in conversation_history[-5:]:  # Last 5 turns for context
                    prompt += f"\n\n{msg['role']}: {msg['content']}"
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
        
        # Add turn to state
        state.add_turn(
            reasoning=reasoning,
            action=action_name,
            action_input=action_params,
            action_output=tool_result_dict,
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
        
        In a production system, this would use a model to evaluate progress.
        For now, we use simple heuristics.
        
        Args:
            state: Current test state
            goal: Test goal
            
        Returns:
            GoalProgress object
        """
        # Simple evaluation based on turn count and errors
        # In production, use model evaluation
        
        if not state.turns:
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.0,
                reasoning="No turns executed yet",
            )
        
        last_turn = state.turns[-1]
        
        # Check if last action was successful
        if not last_turn.action_output.get("success", False):
            error_count = sum(
                1 for turn in state.turns
                if not turn.action_output.get("success", False)
            )
            
            if error_count >= 3:
                return GoalProgress(
                    goal_achieved=False,
                    goal_impossible=True,
                    confidence=0.8,
                    reasoning=f"Multiple failures ({error_count}) suggest goal may be impossible",
                    findings=["Multiple tool execution failures"],
                )
        
        # Simple heuristic: if we've made several successful interactions, consider progress
        successful_turns = sum(
            1 for turn in state.turns
            if turn.action_output.get("success", False)
        )
        
        if successful_turns >= 3:
            # In production, use LLM to evaluate if goal is actually achieved
            return GoalProgress(
                goal_achieved=False,  # Needs proper evaluation
                goal_impossible=False,
                confidence=0.5,
                reasoning=f"Made progress with {successful_turns} successful turns",
                findings=[f"Executed {successful_turns} successful actions"],
            )
        
        return GoalProgress(
            goal_achieved=False,
            goal_impossible=False,
            confidence=0.3,
            reasoning="Test in progress",
        )
    
    def execute_test(
        self,
        target: Target,
        test_instructions: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        max_turns: Optional[int] = None,
    ) -> TestResult:
        """
        Execute a multi-turn test.
        
        This is the main entry point for running tests with Penelope.
        
        Args:
            target: The target to test (must implement Target interface)
            test_instructions: Specific instructions for this test
            goal: Success criteria for the test
            context: Optional additional context/resources
            max_turns: Override default max_iterations for this test
            
        Returns:
            TestResult with complete test execution details
            
        Example:
            >>> from rhesis.penelope import EndpointTarget
            >>> 
            >>> target = EndpointTarget(
            ...     endpoint_id="chatbot-prod",
            ...     config={
            ...         "url": "https://api.example.com/chat",
            ...         "method": "POST",
            ...         "headers": {"Authorization": "Bearer token"},
            ...         "request_template": {"message": ""},
            ...         "response_path": "response",
            ...     }
            ... )
            >>> 
            >>> result = agent.execute_test(
            ...     target=target,
            ...     test_instructions="Test the chatbot's ability to handle refund queries",
            ...     goal="Verify chatbot provides accurate refund policy information",
            ... )
        """
        # Validate target
        is_valid, error = target.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid target configuration: {error}")
        
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


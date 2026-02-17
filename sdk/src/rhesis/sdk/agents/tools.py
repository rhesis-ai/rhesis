"""Concrete tool implementations for agents.

Tools in this module wrap SDK entities as async BaseTool subclasses so
they can be used by any agent (ArchitectAgent, future agents, and
eventually Penelope when it migrates to the agents framework).
"""

import asyncio
import json
import logging
from typing import Any, List, Optional, Union

from rhesis.sdk.agents.base import BaseTool
from rhesis.sdk.agents.schemas import ToolResult

logger = logging.getLogger(__name__)


class ExploreEndpointTool(BaseTool):
    """Explore a Rhesis endpoint's capabilities using Penelope.

    Delegates multi-turn exploration to a ``PenelopeAgent`` which handles
    conversation tracking, stopping conditions, and response extraction.
    The calling agent (e.g. ArchitectAgent) provides high-level goals and
    instructions; Penelope handles the tactical probing.

    Since ``PenelopeAgent.execute_test()`` is synchronous, execution is
    wrapped in ``asyncio.to_thread`` to avoid blocking the event loop.

    Args:
        endpoint_id: UUID of the endpoint to explore.
        endpoint: Pre-loaded ``Endpoint`` instance. Takes precedence
            over ``endpoint_id``.
        model: Model for Penelope to use during exploration. Accepts a
            model string (e.g. ``"vertex_ai/gemini-2.0-flash"``) or a
            ``BaseLLM`` instance. If ``None``, Penelope uses its default.
        max_turns: Maximum conversation turns for each exploration.
            Defaults to 5.

    Example::

        from rhesis.sdk.agents import ExploreEndpointTool
        from rhesis.sdk.entities import Endpoint

        endpoint = Endpoint(id="my-endpoint-id")
        endpoint.pull()
        tool = ExploreEndpointTool(endpoint=endpoint)
    """

    def __init__(
        self,
        endpoint_id: Optional[str] = None,
        endpoint: Optional[Any] = None,
        model: Optional[Union[str, Any]] = None,
        max_turns: int = 5,
    ):
        if endpoint is None and endpoint_id is None:
            raise ValueError("Must provide either endpoint_id or endpoint")

        if endpoint is not None:
            self._endpoint = endpoint
            self._endpoint_id = endpoint.id or endpoint_id or "unknown"
        else:
            from rhesis.sdk.entities import Endpoint

            self._endpoint = Endpoint(id=endpoint_id)
            self._endpoint.pull()
            self._endpoint_id = endpoint_id

        self._model = model
        self._max_turns = max_turns

    @property
    def name(self) -> str:
        return "explore_endpoint"

    @property
    def description(self) -> str:
        ep_name = getattr(self._endpoint, "name", None) or self._endpoint_id
        ep_desc = getattr(self._endpoint, "description", None) or ""
        parts = [
            f"Explore the '{ep_name}' endpoint by running a "
            f"multi-turn conversation against it using Penelope.",
        ]
        if ep_desc:
            parts.append(f"Endpoint description: {ep_desc}")
        parts.append(
            "Provide a goal describing what you want to learn "
            "and optional instructions for how to probe. "
            "Returns the full conversation and findings."
        )
        return " ".join(parts)

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": (
                        "What you want to learn about the endpoint. "
                        "Example: 'Understand the endpoint's domain, "
                        "capabilities, restrictions, and response "
                        "patterns.'"
                    ),
                },
                "instructions": {
                    "type": "string",
                    "description": (
                        "Optional step-by-step instructions for how "
                        "to probe the endpoint. If omitted, Penelope "
                        "plans its own approach based on the goal."
                    ),
                },
                "scenario": {
                    "type": "string",
                    "description": (
                        "Optional persona or situational context. "
                        "Example: 'You are a new user unfamiliar "
                        "with the product.'"
                    ),
                },
                "restrictions": {
                    "type": "string",
                    "description": (
                        "Optional constraints on what the target "
                        "should not do, to verify during exploration."
                    ),
                },
            },
            "required": ["goal"],
        }

    async def execute(
        self,
        goal: str = "",
        instructions: Optional[str] = None,
        scenario: Optional[str] = None,
        restrictions: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Run a multi-turn exploration of the endpoint via Penelope.

        Args:
            goal: What to learn about the endpoint.
            instructions: How to probe (optional).
            scenario: Persona or situational context (optional).
            restrictions: Constraints to verify (optional).
            **kwargs: Ignored (forward-compatibility).

        Returns:
            ``ToolResult`` with conversation summary and findings.
        """
        if not goal or not goal.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Goal cannot be empty",
            )

        try:
            result = await asyncio.to_thread(
                self._run_exploration,
                goal=goal,
                instructions=instructions,
                scenario=scenario,
                restrictions=restrictions,
            )
        except Exception as e:
            logger.error(
                "Endpoint exploration failed: %s",
                e,
                exc_info=True,
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Endpoint exploration failed: {e}",
            )

        content = self._format_result(result)
        return ToolResult(
            tool_name=self.name,
            success=True,
            content=json.dumps(content),
        )

    def _run_exploration(
        self,
        goal: str,
        instructions: Optional[str],
        scenario: Optional[str],
        restrictions: Optional[str],
    ) -> Any:
        """Create target and Penelope agent, then run exploration.

        Runs synchronously — called via ``asyncio.to_thread``.
        """
        from rhesis.penelope import EndpointTarget, PenelopeAgent

        target = EndpointTarget(endpoint=self._endpoint)
        agent = PenelopeAgent(
            model=self._model,
            max_iterations=self._max_turns,
        )
        return agent.execute_test(
            target=target,
            goal=goal,
            instructions=instructions,
            scenario=scenario,
            restrictions=restrictions,
        )

    @staticmethod
    def _format_result(result: Any) -> dict:
        """Extract the useful parts of a TestResult into a dict."""
        conversation: List[dict] = []
        for turn in result.conversation_summary:
            conversation.append(
                {
                    "turn": turn.turn,
                    "sent": turn.penelope_message,
                    "received": turn.target_response,
                }
            )

        output: dict = {
            "status": result.status.value,
            "goal_achieved": result.goal_achieved,
            "turns_used": result.turns_used,
            "findings": result.findings,
            "conversation": conversation,
        }

        if result.goal_evaluation:
            output["goal_evaluation"] = result.goal_evaluation

        return output

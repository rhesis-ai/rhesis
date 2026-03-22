"""Concrete tool implementations for agents.

Tools in this module wrap SDK entities as async BaseTool subclasses so
they can be used by any agent (ArchitectAgent, future agents, and
eventually Penelope when it migrates to the agents framework).
"""

import asyncio
import json
import logging
from typing import Any, Callable, List, Optional, Union

from rhesis.sdk.agents.base import BaseTool
from rhesis.sdk.agents.schemas import ToolResult
from rhesis.sdk.targets import Target

logger = logging.getLogger(__name__)

TargetFactory = Callable[[str], Target]
"""``(endpoint_id) -> Target`` — creates a Target for the given endpoint."""


class ExploreEndpointTool(BaseTool):
    """Explore a Rhesis endpoint's capabilities using Penelope.

    Delegates multi-turn exploration to a ``PenelopeAgent`` which handles
    conversation tracking, stopping conditions, and response extraction.
    The calling agent (e.g. ArchitectAgent) provides high-level goals and
    instructions; Penelope handles the tactical probing.

    Since ``PenelopeAgent.execute_test()`` is synchronous, execution is
    wrapped in ``asyncio.to_thread`` to avoid blocking the event loop.

    The tool supports two modes:

    **Bound mode** (SDK / notebook): provide ``endpoint_id`` or
    ``endpoint`` at construction. The tool is tied to one endpoint.

    **Unbound mode** (backend worker): provide a ``target_factory``
    instead. The LLM passes ``endpoint_id`` at call time and the
    factory creates the appropriate target.  This avoids SDK REST
    client dependencies in server-side contexts.

    Args:
        endpoint_id: UUID of the endpoint to explore (bound mode).
        endpoint: Pre-loaded ``Endpoint`` instance (bound mode).
        target_factory: ``(endpoint_id) -> Target`` callable that
            creates a target for any endpoint (unbound mode).
        model: Model for Penelope to use during exploration. Accepts a
            model string (e.g. ``"vertex_ai/gemini-2.0-flash"``) or a
            ``BaseLLM`` instance. If ``None``, Penelope uses its default.
        max_turns: Maximum conversation turns for each exploration.
            Defaults to 5.

    Example (bound — SDK)::

        from rhesis.sdk.agents import ExploreEndpointTool
        from rhesis.sdk.entities import Endpoint

        endpoint = Endpoint(id="my-endpoint-id")
        endpoint.pull()
        tool = ExploreEndpointTool(endpoint=endpoint)

    Example (unbound — backend worker)::

        tool = ExploreEndpointTool(
            target_factory=my_factory,
            model=model,
        )
    """

    def __init__(
        self,
        endpoint_id: Optional[str] = None,
        endpoint: Optional[Any] = None,
        target_factory: Optional[TargetFactory] = None,
        model: Optional[Union[str, Any]] = None,
        max_turns: int = 5,
    ):
        self._target_factory = target_factory
        self._endpoint: Optional[Any] = None
        self._endpoint_id: Optional[str] = None

        if endpoint is not None:
            self._endpoint = endpoint
            self._endpoint_id = endpoint.id or endpoint_id or "unknown"
        elif endpoint_id is not None:
            from rhesis.sdk.entities import Endpoint

            self._endpoint = Endpoint(id=endpoint_id)
            self._endpoint.pull()
            self._endpoint_id = endpoint_id
        elif target_factory is None:
            raise ValueError("Must provide endpoint_id, endpoint, or target_factory")

        self._model = model
        self._max_turns = max_turns

    @property
    def name(self) -> str:
        return "explore_endpoint"

    @property
    def requires_confirmation(self) -> bool:
        return True

    @property
    def description(self) -> str:
        if self._endpoint is not None:
            ep_name = getattr(self._endpoint, "name", None) or self._endpoint_id
            ep_desc = getattr(self._endpoint, "description", None) or ""
            parts = [
                f"Explore the '{ep_name}' endpoint by running a "
                f"multi-turn conversation against it using Penelope.",
            ]
            if ep_desc:
                parts.append(f"Endpoint description: {ep_desc}")
        else:
            parts = [
                "Explore a Rhesis endpoint by running a multi-turn "
                "conversation against it using Penelope.",
                "You must provide an endpoint_id (resolve it first via list_endpoints).",
            ]
        parts.append(
            "Provide a goal describing what you want to learn "
            "and optional instructions for how to probe. "
            "Returns the full conversation and findings. "
            "IMPORTANT: After running this tool, you MUST present a summary "
            "of the findings to the user."
        )
        return " ".join(parts)

    @property
    def parameters_schema(self) -> dict:
        properties: dict = {
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
        }
        required = ["goal"]

        if self._endpoint is None:
            properties["endpoint_id"] = {
                "type": "string",
                "description": (
                    "UUID of the endpoint to explore. Resolve "
                    "it first via list_endpoints with $select=name,id."
                ),
            }
            required.append("endpoint_id")

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    async def execute(
        self,
        goal: str = "",
        endpoint_id: Optional[str] = None,
        instructions: Optional[str] = None,
        scenario: Optional[str] = None,
        restrictions: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Run a multi-turn exploration of the endpoint via Penelope.

        Args:
            goal: What to learn about the endpoint.
            endpoint_id: UUID of the endpoint (required in unbound mode).
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

        resolved_id = endpoint_id or self._endpoint_id
        if not resolved_id:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=(
                    "endpoint_id is required — resolve it first "
                    "via list_endpoints with $select=name,id"
                ),
            )

        try:
            target = self._resolve_target(resolved_id)
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Failed to resolve endpoint: {e}",
            )

        try:
            result = await asyncio.to_thread(
                self._run_exploration,
                target=target,
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

    def _resolve_target(self, endpoint_id: Optional[str]) -> Target:
        """Build a Target for the given endpoint.

        Priority: target_factory > pre-loaded endpoint > SDK load.
        """
        if self._target_factory is not None and endpoint_id:
            return self._target_factory(endpoint_id)

        if self._endpoint is not None:
            from rhesis.penelope import EndpointTarget

            return EndpointTarget(endpoint=self._endpoint)

        if endpoint_id:
            from rhesis.penelope import EndpointTarget

            return EndpointTarget(endpoint_id=endpoint_id)

        raise ValueError("No endpoint or target_factory available")

    def _run_exploration(
        self,
        target: Target,
        goal: str,
        instructions: Optional[str],
        scenario: Optional[str],
        restrictions: Optional[str],
    ) -> Any:
        """Create Penelope agent and run exploration.

        Runs synchronously — called via ``asyncio.to_thread``.
        """
        from rhesis.penelope import PenelopeAgent

        agent = PenelopeAgent(
            model=self._model,
            max_turns=self._max_turns,
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

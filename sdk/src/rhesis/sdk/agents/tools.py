"""Concrete tool implementations for agents.

Tools in this module wrap SDK entities as async BaseTool subclasses so
they can be used by any agent (ArchitectAgent, future agents, and
eventually Penelope when it migrates to the agents framework).
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from rhesis.sdk.agents.base import BaseTool
from rhesis.sdk.agents.events import _emit
from rhesis.sdk.agents.schemas import ToolResult
from rhesis.sdk.targets import Target

logger = logging.getLogger(__name__)

TargetFactory = Callable[[str], Target]
"""``(endpoint_id) -> Target`` — creates a Target for the given endpoint."""

COMPREHENSIVE_STRATEGY_SEQUENCE = [
    "domain_probing",
    "capability_mapping",
    "boundary_discovery",
]
"""Strategies used in comprehensive exploration.

``domain_probing`` runs first (other strategies depend on its findings).
``capability_mapping`` and ``boundary_discovery`` then run in parallel.
"""


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

    **Strategy support**: pass ``strategy`` to use a named Penelope
    exploration strategy (e.g. ``"domain_probing"``) or
    ``"comprehensive"`` to run all strategies in sequence. Strategies
    generate the goal and instructions automatically; the calling
    agent can still provide ``previous_findings`` so each strategy
    builds on earlier results.

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

    Example (with strategy)::

        result = await tool.execute(
            endpoint_id="...",
            strategy="domain_probing",
        )

    Example (comprehensive — all strategies in sequence)::

        result = await tool.execute(
            endpoint_id="...",
            strategy="comprehensive",
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
                    "patterns.' "
                    "Optional when a strategy is specified (the "
                    "strategy generates the goal automatically)."
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
            "strategy": {
                "type": "string",
                "description": (
                    "Optional exploration strategy name. Use "
                    "'domain_probing' to discover the endpoint's "
                    "domain and purpose, 'capability_mapping' to "
                    "enumerate features and interaction patterns, "
                    "'boundary_discovery' to find refusal patterns "
                    "and limits, or 'comprehensive' to run all "
                    "three strategies in sequence. When a strategy "
                    "is set, goal and instructions are generated "
                    "automatically (but can still be overridden)."
                ),
            },
            "previous_findings": {
                "type": "object",
                "description": (
                    "Optional structured findings from a prior "
                    "exploration run. Passed to the strategy so it "
                    "can build on earlier results."
                ),
            },
        }
        required: List[str] = []

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
        strategy: Optional[str] = None,
        previous_findings: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Run a multi-turn exploration of the endpoint via Penelope.

        Args:
            goal: What to learn about the endpoint. Optional when a
                strategy is specified (the strategy generates it).
            endpoint_id: UUID of the endpoint (required in unbound mode).
            instructions: How to probe (optional).
            scenario: Persona or situational context (optional).
            restrictions: Constraints to verify (optional).
            strategy: Named exploration strategy or ``"comprehensive"``.
            previous_findings: Structured findings from a prior run.
            **kwargs: Ignored (forward-compatibility).

        Returns:
            ``ToolResult`` with conversation summary and findings.
        """
        if not strategy and (not goal or not goal.strip()):
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Goal cannot be empty (or provide a strategy)",
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

        handlers = kwargs.get("_event_handlers", [])
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def _on_tool_start(
            tool_name: str, arguments: Dict[str, Any], reasoning: str
        ) -> None:
            if not handlers or not loop:
                return
            asyncio.run_coroutine_threadsafe(
                _emit(
                    handlers,
                    "on_tool_start",
                    tool_name=tool_name,
                    arguments=arguments,
                    reasoning=reasoning,
                ),
                loop,
            )

        def _on_tool_end(tool_name: str, result: Any, duration_ms: int = 0) -> None:
            if not handlers or not loop:
                return
            sdk_result = ToolResult(
                tool_name=tool_name,
                success=getattr(result, "success", False) if result else False,
                content=str(getattr(result, "output", "")) if result else "",
                error=getattr(result, "error", None) if result else None,
            )
            asyncio.run_coroutine_threadsafe(
                _emit(
                    handlers,
                    "on_tool_end",
                    tool_name=tool_name,
                    result=sdk_result,
                ),
                loop,
            )

        if strategy == "comprehensive":
            return await self._run_comprehensive(
                target=target,
                target_name=self._target_name(),
                target_description=self._target_description(),
                previous_findings=previous_findings,
                scenario=scenario,
                restrictions=restrictions,
                on_tool_start=_on_tool_start,
                on_tool_end=_on_tool_end,
            )

        if strategy:
            resolved = self._resolve_strategy(strategy)
            if resolved is None:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error=(
                        f"Unknown strategy '{strategy}'. Available: "
                        "domain_probing, capability_mapping, "
                        "boundary_discovery, comprehensive"
                    ),
                )
            return await self._run_with_strategy(
                target=target,
                strategy_obj=resolved,
                goal_override=goal if goal and goal.strip() else None,
                instructions_override=instructions,
                previous_findings=previous_findings,
                scenario=scenario,
                restrictions=restrictions,
                on_tool_start=_on_tool_start,
                on_tool_end=_on_tool_end,
            )

        try:
            result = await asyncio.to_thread(
                self._run_exploration,
                target=target,
                goal=goal,
                instructions=instructions,
                scenario=scenario,
                restrictions=restrictions,
                context=previous_findings,
                on_tool_start=_on_tool_start,
                on_tool_end=_on_tool_end,
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

    def _target_name(self) -> str:
        """Human-readable name for the current endpoint."""
        if self._endpoint is not None:
            return getattr(self._endpoint, "name", None) or self._endpoint_id or "endpoint"
        return self._endpoint_id or "endpoint"

    def _target_description(self) -> str:
        """Description of the current endpoint (may be empty)."""
        if self._endpoint is not None:
            return getattr(self._endpoint, "description", None) or ""
        return ""

    @staticmethod
    def _resolve_strategy(name: str) -> Optional[Any]:
        """Look up a strategy by name, returning ``None`` on miss."""
        try:
            from rhesis.penelope.strategies import get_strategy

            return get_strategy(name)
        except (ImportError, KeyError):
            return None

    async def _run_with_strategy(
        self,
        target: Target,
        strategy_obj: Any,
        goal_override: Optional[str],
        instructions_override: Optional[str],
        previous_findings: Optional[Dict[str, Any]],
        scenario: Optional[str],
        restrictions: Optional[str],
        on_tool_start: Optional[Any] = None,
        on_tool_end: Optional[Any] = None,
    ) -> ToolResult:
        """Execute a single named strategy against the target."""
        t_name = self._target_name()
        t_desc = self._target_description()

        goal = goal_override or strategy_obj.build_goal(
            target_name=t_name,
            target_description=t_desc,
            previous_findings=previous_findings,
        )
        instructions = instructions_override or strategy_obj.build_instructions(
            target_name=t_name,
            target_description=t_desc,
            previous_findings=previous_findings,
        )

        max_turns = min(strategy_obj.recommended_max_turns, self._max_turns)

        try:
            result = await asyncio.to_thread(
                self._run_exploration,
                target=target,
                goal=goal,
                instructions=instructions,
                scenario=scenario,
                restrictions=restrictions,
                context=previous_findings,
                max_turns_override=max_turns,
                on_tool_start=on_tool_start,
                on_tool_end=on_tool_end,
            )
        except Exception as e:
            logger.error(
                "Strategy '%s' exploration failed: %s",
                strategy_obj.name,
                e,
                exc_info=True,
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Strategy '{strategy_obj.name}' exploration failed: {e}",
            )

        raw = self._format_result(result)
        findings = strategy_obj.format_findings(raw)
        self._record_performance(strategy_obj.name, findings)
        content = {**raw, "strategy_findings": findings}
        return ToolResult(
            tool_name=self.name,
            success=True,
            content=json.dumps(content),
        )

    async def _run_comprehensive(
        self,
        target: Target,
        target_name: str,
        target_description: str,
        previous_findings: Optional[Dict[str, Any]],
        scenario: Optional[str],
        restrictions: Optional[str],
        on_tool_start: Optional[Any] = None,
        on_tool_end: Optional[Any] = None,
    ) -> ToolResult:
        """Run all exploration strategies, parallelising where possible.

        Domain probing runs first (other strategies depend on its
        findings).  Capability mapping and boundary discovery then run
        concurrently — they both depend on domain findings but not on
        each other.
        """
        accumulated_findings: Dict[str, Any] = dict(previous_findings or {})
        strategy_results: List[Dict[str, Any]] = []
        all_conversations: List[dict] = []
        total_turns = 0

        async def _execute_strategy(
            name: str,
            findings_snapshot: Dict[str, Any],
        ) -> Optional[tuple]:
            """Run one strategy and return (name, raw, findings) or None."""
            strategy_obj = self._resolve_strategy(name)
            if strategy_obj is None:
                logger.warning("Skipping unknown strategy '%s'", name)
                return None

            goal = strategy_obj.build_goal(
                target_name=target_name,
                target_description=target_description,
                previous_findings=findings_snapshot,
            )
            instructions = strategy_obj.build_instructions(
                target_name=target_name,
                target_description=target_description,
                previous_findings=findings_snapshot,
            )
            max_t = min(strategy_obj.recommended_max_turns, self._max_turns)

            try:
                result = await asyncio.to_thread(
                    self._run_exploration,
                    target=target,
                    goal=goal,
                    instructions=instructions,
                    scenario=scenario,
                    restrictions=restrictions,
                    context=findings_snapshot if findings_snapshot else None,
                    max_turns_override=max_t,
                    on_tool_start=on_tool_start,
                    on_tool_end=on_tool_end,
                )
            except Exception as e:
                logger.error(
                    "Comprehensive: strategy '%s' failed: %s",
                    name, e, exc_info=True,
                )
                return (name, None, {"strategy": name, "error": str(e)})

            raw = self._format_result(result)
            findings = strategy_obj.format_findings(raw)
            self._record_performance(name, findings)
            return (name, raw, findings)

        def _merge_findings(findings: Dict[str, Any]) -> None:
            for key, value in findings.items():
                if key in ("strategy", "status", "raw_findings", "raw_findings_text"):
                    continue
                if value and value != "" and value != []:
                    accumulated_findings[key] = value

        def _collect(outcome: Optional[tuple]) -> None:
            if outcome is None:
                return
            _, raw, findings = outcome
            strategy_results.append(findings)
            if raw is not None:
                _merge_findings(findings)
                all_conversations.extend(raw.get("conversation", []))
                nonlocal total_turns
                total_turns += raw.get("turns_used", 0)

        # Phase 1: domain probing (sequential — others depend on it)
        outcome = await _execute_strategy("domain_probing", accumulated_findings)
        _collect(outcome)

        # Phase 2: capability mapping + boundary discovery (parallel)
        snapshot = dict(accumulated_findings)
        parallel_outcomes = await asyncio.gather(
            _execute_strategy("capability_mapping", snapshot),
            _execute_strategy("boundary_discovery", snapshot),
        )
        for out in parallel_outcomes:
            _collect(out)

        content: Dict[str, Any] = {
            "status": "completed",
            "mode": "comprehensive",
            "strategies_run": [r.get("strategy", "?") for r in strategy_results],
            "total_turns_used": total_turns,
            "accumulated_findings": accumulated_findings,
            "per_strategy_findings": strategy_results,
            "conversation": all_conversations,
        }
        return ToolResult(
            tool_name=self.name,
            success=True,
            content=json.dumps(content),
        )

    @staticmethod
    def _record_performance(strategy_name: str, raw_result: Dict[str, Any]) -> None:
        """Record strategy run performance if the strategies module is available."""
        try:
            from rhesis.penelope.strategies import record_strategy_run

            record_strategy_run(strategy_name, raw_result)
        except ImportError:
            pass

    def _run_exploration(
        self,
        target: Target,
        goal: str,
        instructions: Optional[str],
        scenario: Optional[str],
        restrictions: Optional[str],
        context: Optional[Dict[str, Any]] = None,
        max_turns_override: Optional[int] = None,
        on_tool_start: Optional[Any] = None,
        on_tool_end: Optional[Any] = None,
    ) -> Any:
        """Create Penelope agent and run exploration.

        Runs synchronously — called via ``asyncio.to_thread``.
        """
        from rhesis.penelope import PenelopeAgent

        agent = PenelopeAgent(
            model=self._model,
            max_turns=max_turns_override or self._max_turns,
        )
        return agent.execute_test(
            target=target,
            goal=goal,
            instructions=instructions,
            scenario=scenario,
            restrictions=restrictions,
            context=context,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
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

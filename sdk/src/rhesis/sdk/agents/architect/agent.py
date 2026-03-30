"""ArchitectAgent -- conversational agent for building test suites.

Extends BaseAgent with multi-turn conversation, mode management, and
plan tracking. Tools are injected by the caller.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union

from rhesis.sdk.agents.base import BaseAgent, BaseTool, MCPTool
from rhesis.sdk.agents.constants import (
    Action,
    AgentMode,
    InternalTool,
    Role,
    ToolMeta,
)
from rhesis.sdk.agents.events import AgentEventHandler, _emit
from rhesis.sdk.agents.schemas import (
    AgentAction,
    ExecutionStep,
    ToolCall,
    ToolResult,
)
from rhesis.sdk.models.base import BaseLLM

from .config import ArchitectConfig, _default_discovery_state
from .plan import ArchitectPlan, build_save_plan_tool
from .tool_registry import mode_for, plan_category_for

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """Conversational agent for designing and creating test suites.

    Maintains state across conversation turns. Tools are injected
    by the caller -- the agent doesn't know or care whether they
    call backend services directly or go through MCP over HTTP.

    Supports ``event_handlers`` for real-time lifecycle notifications
    (tool execution, mode changes, plan updates, etc.).

    Usage::

        architect = ArchitectAgent(
            model="vertex_ai/gemini-2.0-flash",
            tools=[*get_rhesis_tools(), extra_tool],
            event_handlers=[WebSocketHandler(ws.send_json)],
        )
        response = architect.chat("I need tests for a chatbot")
        response = architect.chat("Focus on safety and fairness")
        response = architect.chat("Looks good, create everything")
    """

    _SAVE_PLAN_TOOL = build_save_plan_tool()

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        tools: Optional[List[Union[BaseTool, MCPTool]]] = None,
        config: Optional[ArchitectConfig] = None,
        max_iterations: Optional[int] = None,
        max_tool_executions: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        history_window: Optional[int] = None,
        verbose: bool = False,
        event_handlers: Optional[List[AgentEventHandler]] = None,
    ):
        self._cfg = config or ArchitectConfig()
        super().__init__(
            model=model,
            tools=tools,
            max_iterations=max_iterations or self._cfg.max_iterations,
            max_tool_executions=max_tool_executions,
            timeout_seconds=timeout_seconds,
            history_window=history_window,
            verbose=verbose,
            event_handlers=event_handlers,
            prompt_templates_dir=(
                Path(__file__).parent / "prompt_templates"
            ),
        )
        self._conversation_history: List[Dict[str, Any]] = []
        self._plan: Optional[ArchitectPlan] = None
        self._mode: AgentMode = AgentMode.DISCOVERY

        # ── write-guard state ────────────────────────────────────
        # Two-layer defense:
        #  Layer 1 (prompt): The system prompt tells the LLM to
        #    present a plan and ask for confirmation before
        #    creating entities.
        #  Layer 2 (structural): This guard intercepts mutating
        #    tool calls if the LLM ignores the prompt. It is a
        #    safety net, not a replacement for prompt-based control.
        #
        # _confirming_tools: specific tools that were blocked and
        #   presented for confirmation. Only these are unlocked
        #   when the user replies.
        # _creation_approved: True for the turn immediately after
        #   a confirmation prompt, False otherwise.
        # _mutating_tools: lazily built from tool metadata on first
        #   call to get_available_tools().
        self._creation_approved: bool = False
        self._confirming_tools: FrozenSet[str] = frozenset()
        self._mutating_tools: Optional[FrozenSet[str]] = None
        self._auto_approve_all: bool = False

        self._discovery_state: Dict[str, Any] = (
            _default_discovery_state()
        )

        # UUID → entity name for resolving IDs in mapping tools
        self._id_to_name: Dict[str, str] = {}

        # Async task waiting: when the agent calls await_task,
        # the turn ends and the backend monitors the task.
        self._pending_tasks: List[Dict[str, str]] = []
        self._awaiting_task: bool = False
        self._await_message: str = ""

        # Per-turn attachments (mentions + file text)
        self._attachments: Optional[Dict[str, Any]] = None

    # ── public API ───────────────────────────────────────────────

    def chat(
        self,
        message: str,
        attachments: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a message and get a response.

        This is the main conversational interface. Each call is
        one turn in the conversation. The agent may call tools
        internally before responding.

        Args:
            message: User's message text.
            attachments: Optional dict with ``mentions`` (resolved
                entity references) and/or ``files`` (extracted text
                from user-uploaded files).

        Returns:
            The agent's response text.
        """
        return asyncio.run(
            self.chat_async(message, attachments=attachments)
        )

    async def chat_async(
        self,
        message: str,
        attachments: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Async version of chat()."""
        async with self._turn_lock:
            self._attachments = attachments
            self._awaiting_task = False
            self._await_message = ""
            self._pending_tasks.clear()
            self._conversation_history.append(
                {"role": Role.USER, "content": message}
            )

            # If the previous turn asked for confirmation, unlock
            # only the specific tools that were blocked.
            if self._needs_confirmation and self._confirming_tools:
                self._creation_approved = True

            # When auto-resumed after background tasks, mark the
            # corresponding plan items as completed.
            if message.startswith("[TASK_COMPLETED]") and self._plan:
                await self._apply_task_completions(message)

            if self.verbose:
                print(f"\n[Architect:{self._mode}] User: {message}")

            await _emit(
                self._event_handlers,
                "on_agent_start",
                query=message,
            )

            try:
                response = await self._run_loop(message)

                self._conversation_history.append(
                    {"role": Role.ASSISTANT, "content": response}
                )

                # Reset per-turn state
                self._creation_approved = False
                self._attachments = None

                if self.verbose:
                    print(
                        f"[Architect:{self._mode}] "
                        f"Response: {response[:200]}..."
                    )

                return response
            finally:
                await self._disconnect_tools()

    # ── properties ───────────────────────────────────────────────

    @property
    def plan(self) -> Optional[ArchitectPlan]:
        """The current plan, if one has been produced."""
        return self._plan

    @plan.setter
    def plan(self, value: ArchitectPlan) -> None:
        """Set the plan (without emitting an event)."""
        self._plan = value

    async def set_plan_async(self, value: ArchitectPlan) -> None:
        """Set the plan and emit a plan_update event."""
        self._plan = value
        await _emit(
            self._event_handlers, "on_plan_update", plan=value
        )

    @property
    def mode(self) -> str:
        """Current agent mode."""
        return self._mode

    async def set_mode_async(self, new_mode: AgentMode) -> None:
        """Transition to a new mode and emit an event."""
        old_mode = self._mode
        if old_mode != new_mode:
            self._mode = new_mode
            await _emit(
                self._event_handlers,
                "on_mode_change",
                old_mode=old_mode,
                new_mode=new_mode,
            )

    @property
    def pending_tasks(self) -> List[Dict[str, str]]:
        """Tasks the agent is waiting for (generation, execution)."""
        return self._pending_tasks

    @property
    def discovery_state(self) -> Dict[str, Any]:
        """What the agent knows and still needs to learn."""
        return self._discovery_state

    @discovery_state.setter
    def discovery_state(self, value: Dict[str, Any]) -> None:
        self._discovery_state = value

    @property
    def auto_approve_all(self) -> bool:
        """Whether all mutating tools skip confirmation."""
        return self._auto_approve_all

    @auto_approve_all.setter
    def auto_approve_all(self, value: bool) -> None:
        self._auto_approve_all = value

    @property
    def guard_state(self) -> Dict[str, Any]:
        """Snapshot of write-guard state (for serialisation)."""
        return {
            "needs_confirmation": self._needs_confirmation,
            "confirming_tools": list(self._confirming_tools),
            "auto_approve_all": self._auto_approve_all,
        }

    @guard_state.setter
    def guard_state(self, value: Dict[str, Any]) -> None:
        self._needs_confirmation = value.get(
            "needs_confirmation", False
        )
        self._confirming_tools = frozenset(
            value.get("confirming_tools", [])
        )
        self._auto_approve_all = value.get(
            "auto_approve_all", False
        )

    def reset(self) -> None:
        """Reset all state for a fresh conversation."""
        self._conversation_history.clear()
        self._execution_history.clear()
        self._plan = None
        self._mode = AgentMode.DISCOVERY
        self._creation_approved = False
        self._confirming_tools = frozenset()
        self._mutating_tools = None
        self._auto_approve_all = False
        self._attachments = None
        self._discovery_state = _default_discovery_state()
        self._id_to_name.clear()
        self._pending_tasks.clear()
        self._awaiting_task = False
        self._await_message = ""

    # ── write-guard ──────────────────────────────────────────────

    _AWAIT_TASK_TOOL: Dict[str, Any] = {
        "name": InternalTool.AWAIT_TASK,
        "description": (
            "Pause this turn and wait for a background task to "
            "complete (test generation or test execution). The "
            "system will automatically resume when the task "
            "finishes. Call this instead of polling get_job_status "
            "or get_test_run in a loop."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Celery task IDs to wait for (from "
                        "generate_test_set or execute_test_set "
                        "responses)."
                    ),
                },
                "message": {
                    "type": "string",
                    "description": (
                        "Message to show the user while waiting."
                    ),
                },
            },
            "required": ["task_ids", "message"],
        },
        ToolMeta.READONLY_HINT: True,
    }

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Override to inject internal tools and discover mutating ones.

        Classification priority:
        1. Explicit ``requires_confirmation`` flag
        2. MCP ``readOnlyHint`` annotation
        3. MCP ``destructiveHint`` annotation
        4. ``http_method`` fallback (GET/HEAD/OPTIONS are read-only)
        """
        tools = await super().get_available_tools()
        tools.append(self._SAVE_PLAN_TOOL)
        tools.append(self._AWAIT_TASK_TOOL)

        if self._mutating_tools is None:
            self._mutating_tools = self._classify_mutating(tools)
            logger.debug(
                "[Architect] %d tools require confirmation: %s",
                len(self._mutating_tools),
                sorted(self._mutating_tools),
            )
        return tools

    def _classify_mutating(
        self, tools: List[Dict[str, Any]]
    ) -> FrozenSet[str]:
        """Build the set of tools that require user confirmation."""
        cfg = self._cfg
        mutating: Set[str] = set()
        for t in tools:
            rc = t.get(ToolMeta.REQUIRES_CONFIRMATION)
            if rc is not None:
                if rc:
                    mutating.add(t["name"])
            elif t.get(ToolMeta.READONLY_HINT) is True:
                pass
            elif t.get(ToolMeta.DESTRUCTIVE_HINT) is True:
                mutating.add(t["name"])
            else:
                method = t.get(
                    ToolMeta.HTTP_METHOD, "POST"
                ).upper()
                if method not in cfg.readonly_http_methods:
                    mutating.add(t["name"])
        return frozenset(mutating)

    def _is_mutating(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation."""
        if self._mutating_tools is None:
            return True
        return tool_name in self._mutating_tools

    async def _handle_tool_calls(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Block mutating tools until the user confirms.

        If the LLM tries to call a tool that requires confirmation
        without prior user approval, the call is intercepted and
        converted into a finish action that presents the plan and
        asks for confirmation.  Read-only tools are always allowed.

        When ``auto_approve_all`` is set, all tools are allowed
        without confirmation (session-level override).
        """
        if self._auto_approve_all:
            return await super()._handle_tool_calls(
                action, iteration
            )

        mutating = [
            tc
            for tc in action.tool_calls
            if self._is_mutating(tc.tool_name)
        ]

        if mutating and not self._is_approved(mutating):
            blocked_names = [tc.tool_name for tc in mutating]
            logger.info(
                "[Architect] Blocked tools pending confirmation: %s",
                blocked_names,
            )

            # Unlock ALL mutating tools so the full plan can
            # execute without re-blocking on subsequent types.
            self._confirming_tools = (
                self._mutating_tools or frozenset(blocked_names)
            )

            # Still allow read-only tools to execute
            read_only = [
                tc
                for tc in action.tool_calls
                if not self._is_mutating(tc.tool_name)
            ]
            if read_only:
                read_results = await self._execute_tools(read_only)
                self._execution_history.append(
                    ExecutionStep(
                        iteration=iteration,
                        reasoning=action.reasoning,
                        action=Action.CALL_TOOL,
                        tool_calls=read_only,
                        tool_results=read_results,
                    )
                )

            finish_action = AgentAction(
                reasoning=(
                    f"{action.reasoning}\n\n"
                    f"[BLOCKED] The following tools require user "
                    f"confirmation: {blocked_names}. "
                    f"Present the plan and ask the user to confirm."
                ),
                action=Action.FINISH,
                final_answer=(
                    action.final_answer or action.reasoning
                ),
                needs_confirmation=True,
            )
            return await self._handle_finish_action(
                finish_action, iteration
            )

        return await super()._handle_tool_calls(action, iteration)

    def _is_approved(self, tool_calls: list) -> bool:
        """Check if the requested tool calls are approved."""
        if self._auto_approve_all:
            return True
        if not self._creation_approved:
            return False
        return all(
            tc.tool_name in self._confirming_tools
            for tc in tool_calls
        )

    # ── argument validation ──────────────────────────────────────

    def _validate_tool_arguments(
        self, tool_call: ToolCall
    ) -> Optional[str]:
        """Structural defense against oversized/malformed payloads.

        Returns an error message if validation fails, None if ok.
        """
        cfg = self._cfg
        args = tool_call.arguments
        try:
            serialized = json.dumps(args, default=str)
        except (TypeError, ValueError):
            return "Tool arguments could not be serialized"

        payload_size = len(serialized.encode("utf-8"))
        if payload_size > cfg.max_payload_bytes:
            limit_kb = cfg.max_payload_bytes // 1000
            return (
                f"Tool arguments exceed the {limit_kb} KB "
                f"payload limit. Break the operation into "
                f"smaller calls."
            )

        for key, value in args.items():
            if (
                isinstance(value, str)
                and len(value) > cfg.max_string_value_len
            ):
                limit_kb = cfg.max_string_value_len // 1000
                return (
                    f"Argument '{key}' exceeds the "
                    f"{limit_kb} KB string limit."
                )
            if (
                isinstance(value, list)
                and len(value) > cfg.max_array_items
            ):
                return (
                    f"Argument '{key}' contains {len(value)} "
                    f"items (max {cfg.max_array_items}). "
                    f"Split into multiple calls."
                )

        return None

    # ── plan constraints ──────────────────────────────────────────

    def _check_plan_constraints(
        self, tool_call: ToolCall
    ) -> Optional[str]:
        """Reject tool calls that contradict the saved plan.

        Returns an error message if the call is invalid, None if ok.
        """
        if not self._plan:
            return None

        if (
            tool_call.tool_name == "create_project"
            and not self._plan.project
        ):
            return (
                "The saved plan does not include a project. "
                "Skip create_project and proceed with the next "
                "step in the plan."
            )

        if tool_call.tool_name == "create_metric":
            name = tool_call.arguments.get("name", "")
            if name and not any(
                m.name.lower() == name.lower()
                for m in self._plan.metrics
            ):
                planned = [m.name for m in self._plan.metrics]
                return (
                    f"Metric name '{name}' does not match any "
                    f"planned metric. Use the exact name from "
                    f"the plan: {planned}."
                )

        already = self._check_already_completed(tool_call)
        if already:
            return already

        prereqs = self._check_execution_order(tool_call)
        if prereqs:
            return prereqs

        return None

    def _check_already_completed(
        self, tool_call: ToolCall
    ) -> Optional[str]:
        """Reject creation of an entity that is already completed."""
        plan = self._plan
        if not plan:
            return None

        category = plan_category_for(tool_call.tool_name)
        if not category:
            return None

        name = (tool_call.arguments.get("name") or "").lower()
        if not name:
            return None

        items_map = {
            "project": [plan.project] if plan.project else [],
            "behavior": plan.behaviors,
            "test_set": plan.test_sets,
            "metric": plan.metrics,
        }
        items = items_map.get(category, [])

        for item in items:
            if (
                item
                and item.completed
                and item.name.lower() == name
            ):
                return (
                    f"'{item.name}' is already completed in the "
                    f"plan. Skip this step and proceed to the "
                    f"next item."
                )

        return None

    def _check_execution_order(
        self, tool_call: ToolCall
    ) -> Optional[str]:
        """Block test set creation while prerequisites are incomplete.

        Behaviors, metrics, and mappings must all be completed
        before generating test sets.
        """
        plan = self._plan
        if not plan:
            return None

        if tool_call.tool_name not in (
            "generate_test_set",
            "create_test_set_bulk",
        ):
            return None

        pending: List[str] = []
        for b in plan.behaviors:
            if not b.completed:
                pending.append(f"behavior '{b.name}'")
        for m in plan.metrics:
            if not m.completed:
                pending.append(f"metric '{m.name}'")
        for mp in plan.behavior_metric_mappings:
            if not mp.completed:
                pending.append(
                    f"mapping '{mp.behavior}' → "
                    f"{', '.join(mp.metrics)}"
                )

        if pending:
            return (
                "Cannot generate test sets yet. Complete these "
                "plan items first: "
                + "; ".join(pending)
                + "."
            )
        return None

    # ── tool execution ───────────────────────────────────────────

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Intercept internal tools, validate args, enforce constraints."""
        if tool_call.tool_name == InternalTool.SAVE_PLAN:
            return await self._execute_save_plan(tool_call)

        if tool_call.tool_name == InternalTool.AWAIT_TASK:
            return await self._execute_await_task(tool_call)

        error = (
            self._check_plan_constraints(tool_call)
            or self._validate_tool_arguments(tool_call)
        )
        if error:
            logger.warning(
                "[Architect] Rejected tool %s: %s",
                tool_call.tool_name,
                error,
            )
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=error,
            )

        target_mode = mode_for(tool_call.tool_name)
        if target_mode is not None:
            await self.set_mode_async(target_mode)

        result = await super().execute_tool(tool_call)
        if result.success and self._plan:
            await self._track_plan_progress(tool_call, result)
        return result

    # ── plan management ──────────────────────────────────────────

    async def _execute_save_plan(
        self, tool_call: ToolCall
    ) -> ToolResult:
        """Parse LLM-provided plan data and store it."""
        try:
            plan = ArchitectPlan.model_validate(tool_call.arguments)
            for b in plan.behaviors:
                if b.reuse_status == "reuse":
                    b.completed = True
            for m in plan.metrics:
                if m.reuse_status == "reuse":
                    m.completed = True
            await self.set_mode_async(AgentMode.PLANNING)
            await self.set_plan_async(plan)
            logger.info(
                "[Architect] Plan saved: %d behaviors, "
                "%d test sets, %d metrics",
                len(plan.behaviors),
                len(plan.test_sets),
                len(plan.metrics),
            )
            project_label = (
                f"{plan.project.name} — " if plan.project else ""
            )
            return ToolResult(
                tool_name=InternalTool.SAVE_PLAN,
                success=True,
                content=(
                    f"Plan saved: {project_label}"
                    f"{len(plan.behaviors)} behaviors, "
                    f"{len(plan.test_sets)} test sets, "
                    f"{len(plan.metrics)} metrics"
                ),
            )
        except Exception as e:
            logger.warning(
                "[Architect] Failed to parse plan: %s", e
            )
            return ToolResult(
                tool_name=InternalTool.SAVE_PLAN,
                success=False,
                error=f"Invalid plan data: {e}",
            )

    # ── async task waiting ────────────────────────────────────────

    async def _execute_await_task(
        self, tool_call: ToolCall
    ) -> ToolResult:
        """Pause the turn to wait for background tasks."""
        task_ids = tool_call.arguments.get("task_ids", [])
        message = tool_call.arguments.get("message", "")
        if not task_ids:
            return ToolResult(
                tool_name=InternalTool.AWAIT_TASK,
                success=False,
                error="task_ids is required.",
            )
        for tid in task_ids:
            self._pending_tasks.append({"task_id": str(tid)})
        self._awaiting_task = True
        self._await_message = message
        logger.info(
            "[Architect] Awaiting %d task(s): %s",
            len(task_ids),
            task_ids,
        )
        return ToolResult(
            tool_name=InternalTool.AWAIT_TASK,
            success=True,
            content=(
                f"Turn paused. Waiting for {len(task_ids)} "
                f"background task(s). The system will resume "
                f"this conversation automatically."
            ),
        )

    async def _execute_iteration(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        iteration: int,
    ) -> Tuple[ExecutionStep, bool]:
        """Override to force-finish when await_task has been called."""
        step, should_finish = await super()._execute_iteration(
            user_query, available_tools, iteration
        )
        if self._awaiting_task and not should_finish:
            step = ExecutionStep(
                iteration=iteration,
                reasoning="Pausing turn to wait for background tasks.",
                action=Action.FINISH,
                tool_calls=step.tool_calls,
                tool_results=[
                    ToolResult(
                        tool_name=InternalTool.AWAIT_TASK,
                        success=True,
                        content=self._await_message,
                    )
                ],
            )
            should_finish = True
            self._needs_confirmation = False
        return step, should_finish

    async def _track_plan_progress(
        self, tool_call: ToolCall, result: ToolResult
    ) -> None:
        """Mark plan items as completed after successful tool calls."""
        self._collect_id_names(result)

        plan = self._plan
        if not plan:
            return

        category = plan_category_for(tool_call.tool_name)
        if not category:
            return

        name = (tool_call.arguments.get("name") or "").lower()
        updated = False

        if (
            category == "project"
            and plan.project
            and not plan.project.completed
        ):
            plan.project.completed = True
            updated = True

        elif category == "behavior" and name:
            updated = self._mark_completed(plan.behaviors, name)

        elif category == "test_set" and name:
            if tool_call.tool_name == "generate_test_set":
                pass  # async — marked when [TASK_COMPLETED] arrives
            else:
                updated = self._mark_completed(plan.test_sets, name)

        elif category == "metric":
            updated = self._match_metric(plan, tool_call, name)

        elif category == "mapping":
            updated = self._match_mapping(
                plan, tool_call, self._id_to_name
            )

        if updated:
            await _emit(
                self._event_handlers, "on_plan_update", plan=plan
            )

    @staticmethod
    def _mark_completed(items: list, name: str) -> bool:
        """Mark the first matching incomplete item as completed."""
        for item in items:
            if not item.completed and item.name.lower() == name:
                item.completed = True
                return True
        return False

    @staticmethod
    def _match_metric(
        plan: ArchitectPlan,
        tool_call: ToolCall,
        name: str,
    ) -> bool:
        """Match a metric by name or by generation prompt."""
        if not name and tool_call.arguments.get("prompt"):
            prompt_lower = tool_call.arguments["prompt"].lower()
            for m in plan.metrics:
                if (
                    not m.completed
                    and m.name.lower() in prompt_lower
                ):
                    m.completed = True
                    return True
        if name:
            for m in plan.metrics:
                if not m.completed and m.name.lower() == name:
                    m.completed = True
                    return True
        return False

    def _collect_id_names(self, result: ToolResult) -> None:
        """Extract id→name pairs from tool results for later lookup."""
        if not result.success or not result.content:
            return
        try:
            data = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return
        if isinstance(data, dict) and "value" in data:
            data = data["value"]
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                eid = item.get("id")
                ename = item.get("name")
                if eid and ename:
                    self._id_to_name[str(eid)] = ename

    @staticmethod
    def _match_mapping(
        plan: ArchitectPlan,
        tool_call: ToolCall,
        id_to_name: Dict[str, str],
    ) -> bool:
        """Mark a mapping as completed when add_behavior_to_metric succeeds."""
        behavior_id = tool_call.arguments.get("behavior_id", "")
        metric_id = tool_call.arguments.get("metric_id", "")
        behavior = id_to_name.get(behavior_id, "").lower()
        metric = id_to_name.get(metric_id, "").lower()
        if not behavior and not metric:
            return False
        for mapping in plan.behavior_metric_mappings:
            if mapping.completed:
                continue
            if behavior and mapping.behavior.lower() == behavior:
                mapping.completed = True
                return True
            if metric and any(
                m.lower() == metric for m in mapping.metrics
            ):
                mapping.completed = True
                return True
        return False

    async def _apply_task_completions(self, message: str) -> None:
        """Parse a [TASK_COMPLETED] message and mark plan items done."""
        import re

        plan = self._plan
        if not plan:
            return

        updated = False
        for line in message.splitlines():
            match = re.search(
                r"Test set '([^']+)' generated successfully", line
            )
            if match:
                name = match.group(1).lower()
                for ts in plan.test_sets:
                    if not ts.completed and ts.name.lower() == name:
                        ts.completed = True
                        updated = True
                        break

        if updated:
            await _emit(
                self._event_handlers, "on_plan_update", plan=plan
            )

    # ── transport lifecycle ──────────────────────────────────────

    async def _disconnect_tools(self) -> None:
        """Close MCP tool transports at end of each turn."""
        for tool in self._tools:
            if isinstance(tool, MCPTool):
                try:
                    await tool.disconnect()
                except Exception:
                    pass

    # ── prompt building ──────────────────────────────────────────

    def _build_prompt(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
    ) -> str:
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history()
        plan_text = self._plan.to_markdown() if self._plan else ""
        discovery_text = self._format_discovery_state()
        attachments_text = self._format_attachments()

        template = self._jinja_env.get_template(
            "iteration_prompt.j2"
        )
        return template.render(
            mode=self._mode,
            user_query=user_query,
            tools_text=tools_text,
            history_text=history_text,
            plan_text=plan_text,
            discovery_state_text=discovery_text,
            attachments_text=attachments_text,
        )

    def _format_discovery_state(self) -> str:
        """Format the discovery state for the iteration prompt."""
        ds = self._discovery_state
        if not ds.get("endpoint_id") and not ds.get("observations"):
            return ""

        parts: List[str] = []
        if ds.get("endpoint_name"):
            parts.append(
                f"Endpoint: {ds['endpoint_name']} "
                f"(id: {ds['endpoint_id']})"
            )
        parts.append(
            "Explored: yes" if ds.get("explored") else "Explored: not yet"
        )
        for label, key in [
            ("Observations", "observations"),
            ("User-confirmed testing areas", "user_confirmed_areas"),
            ("Open questions", "open_questions"),
        ]:
            items = ds.get(key)
            if items:
                parts.append(f"{label}:")
                for item in items:
                    parts.append(f"  - {item}")
        return "\n".join(parts)

    def _format_attachments(self) -> str:
        """Format per-turn attachments for the prompt."""
        if not self._attachments:
            return ""

        cfg = self._cfg
        parts: List[str] = []

        mentions = self._attachments.get("mentions")
        if mentions:
            parts.append("Resolved entity references:")
            for m in mentions:
                parts.append(
                    f"  - @{m['type']}:{m['display']} "
                    f"(id: {m['id']})"
                )

        files = self._attachments.get("files")
        if files:
            for f in files:
                filename = f.get("filename", "unknown")
                content = f.get("content", "")
                if len(content) > cfg.max_attachment_chars:
                    content = (
                        content[: cfg.max_attachment_chars]
                        + "\n\n[... truncated ...]"
                    )
                parts.append(
                    f"Attached file: {filename}\n"
                    f"```\n{content}\n```"
                )

        return "\n".join(parts)

    # ── streaming finish (Phase 2 LLM call) ──────────────────────

    async def _handle_finish_action(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Stream the final response token-by-token."""
        logger.info("[Architect] Streaming final response")
        confirmation = (
            action.needs_confirmation and not self._auto_approve_all
        )
        self._needs_confirmation = confirmation

        seed = action.final_answer or ""
        streaming_prompt = self._build_streaming_prompt(
            reasoning=action.reasoning,
            final_answer=seed,
        )

        streamed_content = await self._stream_final_response(
            prompt=streaming_prompt,
            system_prompt="",
            fallback_content=seed,
            needs_confirmation=confirmation,
        )

        if self.verbose:
            preview = streamed_content[:200] if streamed_content else ""
            print(f"\nStreamed Answer: {preview}...")

        return (
            ExecutionStep(
                iteration=iteration,
                reasoning=action.reasoning,
                action=Action.FINISH,
                tool_calls=[],
                tool_results=[
                    ToolResult(
                        tool_name=InternalTool.FINISH,
                        success=True,
                        content=streamed_content,
                    )
                ],
            ),
            True,
        )

    def _build_streaming_prompt(
        self,
        reasoning: str,
        final_answer: str,
    ) -> str:
        """Build the prompt for the streaming Phase 2 LLM call."""
        conv_window = self._conversation_history[
            -self._history_window :
        ]
        plan_text = self._plan.to_markdown() if self._plan else ""
        tool_results_text = (
            self._format_tool_results_for_streaming()
        )

        template = self._jinja_env.get_template(
            "streaming_response.j2"
        )
        return template.render(
            conversation_history=conv_window,
            plan_text=plan_text,
            tool_results=tool_results_text,
            reasoning=reasoning,
            final_answer=final_answer,
        )

    def _format_tool_results_for_streaming(self) -> str:
        """Format tool results from the current turn."""
        if not self._execution_history:
            return ""
        cfg = self._cfg
        parts: List[str] = []
        for step in self._execution_history:
            if step.tool_results:
                for tr in step.tool_results:
                    preview = cfg.tool_result_preview_chars
                    if tr.success and tr.content:
                        parts.append(
                            f"[{tr.tool_name}]: "
                            f"{tr.content[:preview]}"
                        )
                    elif tr.error:
                        parts.append(
                            f"[{tr.tool_name}] Error: {tr.error}"
                        )
        return "\n\n".join(parts)

    # ── history formatting ───────────────────────────────────────

    def _format_history(self) -> str:
        parts: List[str] = []
        cfg = self._cfg

        conv_window = self._conversation_history[
            -self._history_window :
        ]
        if len(self._conversation_history) > self._history_window:
            omitted = (
                len(self._conversation_history) - self._history_window
            )
            parts.append(
                f"[... {omitted} earlier messages omitted ...]"
            )

        recent_start = max(
            0, len(conv_window) - cfg.recent_msg_limit
        )
        for i, msg in enumerate(conv_window):
            role = msg["role"].capitalize()
            content = msg["content"]
            max_chars = (
                cfg.recent_msg_max_chars
                if i >= recent_start
                else cfg.older_msg_max_chars
            )
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
            parts.append(f"{role}: {content}")

        exec_window = self._execution_history[
            -self._history_window :
        ]
        if len(self._execution_history) > self._history_window:
            omitted = (
                len(self._execution_history) - self._history_window
            )
            parts.append(
                f"[... {omitted} earlier tool steps omitted ...]"
            )
        for step in exec_window:
            reasoning_preview = step.reasoning[
                : cfg.reasoning_preview_chars
            ]
            parts.append(
                f"[Tool iteration {step.iteration}] "
                f"Reasoning: {reasoning_preview}"
            )
            if step.tool_calls:
                for tc in step.tool_calls:
                    parts.append(f"  Called: {tc.tool_name}")
            if step.tool_results:
                for tr in step.tool_results:
                    preview = cfg.tool_result_preview_chars
                    if tr.success:
                        parts.append(
                            f"  Result ({tr.tool_name}): "
                            f"{tr.content[:preview]}"
                        )
                    else:
                        parts.append(
                            f"  Error ({tr.tool_name}): "
                            f"{tr.error}"
                        )

        return "\n".join(parts) if parts else ""

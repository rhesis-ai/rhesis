"""ArchitectAgent -- conversational agent for building test suites.

Extends BaseAgent with multi-turn conversation, mode management, and
plan tracking. Tools are injected by the caller.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union

from pydantic import ValidationError

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
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)
from rhesis.sdk.models.base import BaseLLM

from .config import ArchitectConfig, _default_discovery_state
from .plan import _INTERNAL_FIELDS, ArchitectPlan, build_save_plan_tool
from .prompt_loader import build_architect_jinja_env, render_phase_knowledge
from .state import ArchitectAgentStateSnapshot
from .tool_registry import mode_for, plan_category_for
from .workflow import WorkflowPath, resolve_workflow_path_update

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────


def _strip_llm_internal_fields(args: Any) -> Any:
    """Remove internal-only fields from an LLM-provided save_plan payload.

    ``completed`` and ``linked_metrics`` track execution progress managed
    exclusively by the agent runtime. When the LLM calls ``save_plan``
    (which replaces the stored plan in full), it must not be able to roll
    back progress by passing stale or fabricated values for these fields.
    Strip them recursively from any dict/list structure so the Pydantic
    defaults always win on a fresh save.
    """
    if isinstance(args, dict):
        return {
            k: _strip_llm_internal_fields(v) for k, v in args.items() if k not in _INTERNAL_FIELDS
        }
    if isinstance(args, list):
        return [_strip_llm_internal_fields(item) for item in args]
    return args


def _unwrap_list_envelope(data: Any) -> Tuple[Optional[List[Any]], Dict[str, Any]]:
    """Normalise recognised list-response shapes to (items, pagination).

    Returns:
        ``(items, pagination)`` when the payload is a known list shape.
        ``(None, {})`` for a plain object or unknown shape — callers should
        fall back to treating the whole payload as a single item.

    Recognised shapes:
      - bare list                     ``[{...}, ...]``
      - MCP paginated list envelope   ``{"results": [...], "_pagination": {...}}``
      - legacy OData envelope         ``{"value": [...]}``
    """
    if isinstance(data, list):
        return data, {}
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            return data["results"], data.get("_pagination") or {}
        if isinstance(data.get("value"), list):
            return data["value"], {}
    return None, {}


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
        templates_dir = Path(__file__).parent / "prompt_templates"
        super().__init__(
            model=model,
            tools=tools,
            max_iterations=max_iterations or self._cfg.max_iterations,
            max_tool_executions=max_tool_executions,
            timeout_seconds=timeout_seconds,
            history_window=history_window,
            verbose=verbose,
            event_handlers=event_handlers,
            prompt_templates_dir=templates_dir,
            jinja_env=build_architect_jinja_env(templates_dir),
        )
        self._conversation_history: List[Dict[str, Any]] = []
        self._plan: Optional[ArchitectPlan] = None
        self._mode: AgentMode = AgentMode.DISCOVERY
        self._workflow_path: WorkflowPath = WorkflowPath.UNSET

        # ── write-guard state ────────────────────────────────────
        # Two-layer defense:
        #  Layer 1 (prompt): The system prompt tells the LLM to
        #    present a plan and ask for confirmation before
        #    creating entities.
        #  Layer 2 (structural): This guard intercepts mutating
        #    tool calls if the LLM ignores the prompt. It is a
        #    safety net, not a replacement for prompt-based control.
        #
        # _confirming_tools: long-lived approval scope — the tools
        #   that have been (or are being) presented for confirmation.
        #   Survives across turns; cleared only by reset()/guard_state.
        # _creation_approved: True for the turn immediately after
        #   a confirmation prompt, False otherwise.
        # _mutating_tools: lazily built from tool metadata on first
        #   call to get_available_tools().
        # _blocked_this_turn: per-turn transient flag — set to True
        #   inside _handle_tool_calls when an actual block happens,
        #   reset to False at the start of every turn. This — not
        #   _confirming_tools — is what drives the response-level
        #   needs_confirmation flag, because Accept/Change is only
        #   meaningful when this turn's LLM step tried to call a
        #   confirmable tool that we just intercepted.
        self._creation_approved: bool = False
        self._confirming_tools: FrozenSet[str] = frozenset()
        self._mutating_tools: Optional[FrozenSet[str]] = None
        self._auto_approve_all: bool = False
        self._blocked_this_turn: bool = False

        self._discovery_state: Dict[str, Any] = _default_discovery_state()

        # UUID → entity name for resolving IDs in mapping tools.
        # Populated from any successful tool result that contains {id, name}.
        self._id_to_name: Dict[str, str] = {}

        # Type-scoped ID→name maps, populated only from behavior / metric
        # tool results respectively. Used in reconciliation to avoid false
        # completions caused by name collisions with other entity types
        # (endpoints, projects, test sets) that share _id_to_name.
        self._behavior_id_names: Dict[str, str] = {}
        self._metric_id_names: Dict[str, str] = {}

        # Successful (behavior_name_lower, metric_name_lower) links observed
        # in this session via ``add_behavior_to_metric``. Tracked outside
        # ``self._plan`` so links made BEFORE ``save_plan`` is called are
        # not lost — ``_execute_save_plan`` consults this set to seed
        # ``MappingSpec.completed`` and ``MappingSpec.linked_metrics``.
        self._linked_pairs: Set[Tuple[str, str]] = set()

        # Raw (behavior_id, metric_id) pairs from add_behavior_to_metric.
        # Fallback when the IDs weren't yet resolved to names at link time.
        self._linked_id_pairs: Set[Tuple[str, str]] = set()

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
        return asyncio.run(self.chat_async(message, attachments=attachments))

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
            # ``_blocked_this_turn`` is the transient signal that drives
            # the response-level needs_confirmation flag. Reset it on
            # every fresh turn so a previous turn's block can never
            # leak into a later finish (e.g. an auto-resumed
            # [TASK_COMPLETED] summary).
            self._blocked_this_turn = False
            self._conversation_history.append({"role": Role.USER, "content": message})
            self._maybe_update_workflow_path(message)

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

            response: str = ""
            agent_error: Optional[Exception] = None
            try:
                response = await self._run_loop(message)

                self._conversation_history.append({"role": Role.ASSISTANT, "content": response})

                # Reset per-turn state
                self._creation_approved = False
                self._attachments = None

                if self.verbose:
                    print(f"[Architect:{self._mode}] Response: {response[:200]}...")

                return response
            except Exception as exc:
                agent_error = exc
                raise
            finally:
                # Always emit ``on_agent_end`` so handlers (notably
                # ``TracingHandler``) can close the ``mcp_agent_run``
                # span attached during ``on_agent_start``.  Skipping
                # this leaks the OTel context token, which (a) leaves
                # the span unended -- the viewer never sees it, so
                # downstream iteration spans appear orphaned at the
                # top level -- and (b) breaks LIFO context detach
                # ordering on the surrounding ``run_chat`` exit.
                #
                # The result mirrors ``BaseAgent.run_async`` so any
                # handler that inspects ``execution_history`` /
                # ``success`` / ``error`` sees the same shape.
                try:
                    finished_ok = any(s.action == Action.FINISH for s in self._execution_history)
                    success = agent_error is None and finished_ok
                    error_msg: Optional[str] = str(agent_error) if agent_error is not None else None
                    result = AgentResult(
                        final_answer=response,
                        execution_history=list(self._execution_history),
                        iterations_used=len(self._execution_history),
                        max_iterations_reached=(
                            len(self._execution_history) >= self.max_iterations and not finished_ok
                        ),
                        success=success,
                        error=error_msg,
                    )
                    await _emit(
                        self._event_handlers,
                        "on_agent_end",
                        result=result,
                    )
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
        await _emit(self._event_handlers, "on_plan_update", plan=value)

    @property
    def mode(self) -> str:
        """Current agent mode."""
        return self._mode

    async def set_mode_async(self, new_mode: AgentMode) -> None:
        """Transition to a new mode and emit an event."""
        old_mode = self._mode
        if old_mode != new_mode:
            self._mode = new_mode
            if new_mode == AgentMode.PLANNING and self._workflow_path == WorkflowPath.UNSET:
                self._workflow_path = WorkflowPath.EXPLORE
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
        self._needs_confirmation = value.get("needs_confirmation", False)
        self._confirming_tools = frozenset(value.get("confirming_tools", []))
        self._auto_approve_all = value.get("auto_approve_all", False)

    def reset(self) -> None:
        """Reset all state for a fresh conversation."""
        self._conversation_history.clear()
        self._execution_history.clear()
        self._plan = None
        self._mode = AgentMode.DISCOVERY
        self._workflow_path = WorkflowPath.UNSET
        self._creation_approved = False
        self._confirming_tools = frozenset()
        self._blocked_this_turn = False
        self._mutating_tools = None
        self._auto_approve_all = False
        self._attachments = None
        self._discovery_state = _default_discovery_state()
        self._id_to_name.clear()
        self._behavior_id_names.clear()
        self._metric_id_names.clear()
        self._linked_pairs.clear()
        self._linked_id_pairs.clear()
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
                    "description": ("Message to show the user while waiting."),
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

    def _classify_mutating(self, tools: List[Dict[str, Any]]) -> FrozenSet[str]:
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
                method = t.get(ToolMeta.HTTP_METHOD, "POST").upper()
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
            return await super()._handle_tool_calls(action, iteration)

        mutating = [tc for tc in action.tool_calls if self._is_mutating(tc.tool_name)]

        if mutating and not self._is_approved(mutating):
            blocked_names = [tc.tool_name for tc in mutating]
            logger.info(
                "[Architect] Blocked tools pending confirmation: %s",
                blocked_names,
            )

            # Mark the per-turn signal that drives the UI's
            # Accept/Change confirmation prompt. ``_confirming_tools``
            # below is a long-lived approval scope, but this flag is
            # specifically "this turn just blocked something".
            self._blocked_this_turn = True

            # Unlock ALL mutating tools so the full plan can
            # execute without re-blocking on subsequent types.
            self._confirming_tools = self._mutating_tools or frozenset(blocked_names)

            # Still allow read-only tools to execute
            read_only = [tc for tc in action.tool_calls if not self._is_mutating(tc.tool_name)]
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

            # ``_confirming_tools`` was populated above; the
            # downstream ``_handle_finish_action`` derives
            # ``needs_confirmation`` from that runtime state, so
            # we don't need to set the flag on the action itself.
            finish_action = AgentAction(
                reasoning=(
                    f"{action.reasoning}\n\n"
                    f"[BLOCKED] The following tools require user "
                    f"confirmation: {blocked_names}. "
                    f"Present the plan and ask the user to confirm."
                ),
                action=Action.FINISH,
                final_answer=(action.final_answer or action.reasoning),
            )
            return await self._handle_finish_action(finish_action, iteration)

        return await super()._handle_tool_calls(action, iteration)

    def _is_approved(self, tool_calls: list) -> bool:
        """Check if the requested tool calls are approved."""
        if self._auto_approve_all:
            return True
        if not self._creation_approved:
            return False
        return all(tc.tool_name in self._confirming_tools for tc in tool_calls)

    # ── argument validation ──────────────────────────────────────

    def _validate_tool_arguments(self, tool_call: ToolCall) -> Optional[str]:
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
            if isinstance(value, str) and len(value) > cfg.max_string_value_len:
                limit_kb = cfg.max_string_value_len // 1000
                return f"Argument '{key}' exceeds the {limit_kb} KB string limit."
            if isinstance(value, list) and len(value) > cfg.max_array_items:
                return (
                    f"Argument '{key}' contains {len(value)} "
                    f"items (max {cfg.max_array_items}). "
                    f"Split into multiple calls."
                )

        return None

    # ── plan constraints ──────────────────────────────────────────

    def _check_plan_constraints(self, tool_call: ToolCall) -> Optional[str]:
        """Reject tool calls that contradict the saved plan.

        Returns an error message if the call is invalid, None if ok.
        """
        if not self._plan:
            return None

        if tool_call.tool_name == "create_project" and not self._plan.project:
            return (
                "The saved plan does not include a project. "
                "Skip create_project and proceed with the next "
                "step in the plan."
            )

        if tool_call.tool_name == "create_metric":
            name = tool_call.arguments.get("name", "")
            if name and not any(m.name.lower() == name.lower() for m in self._plan.metrics):
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

    def _check_already_completed(self, tool_call: ToolCall) -> Optional[str]:
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
            if item and item.completed and item.name.lower() == name:
                return (
                    f"'{item.name}' is already completed in the "
                    f"plan. Skip this step and proceed to the "
                    f"next item."
                )

        return None

    def _check_execution_order(self, tool_call: ToolCall) -> Optional[str]:
        """Block test set creation while prerequisites are incomplete.

        Behaviors, metrics, and mappings must all be completed
        before generating test sets.

        Reconciles the plan against live session evidence immediately before
        checking so that entities created or linked since the last save_plan
        call are reflected — avoiding false blocks when the agent skips an
        intermediate save_plan.
        """
        plan = self._plan
        if not plan:
            return None

        if tool_call.tool_name not in (
            "generate_test_set",
            "create_test_set_bulk",
        ):
            return None

        # Refresh completion flags from session evidence so the guard
        # never fires on work the agent has already done this session.
        self._reconcile_plan_with_session_evidence(plan)

        pending: List[str] = []
        for b in plan.behaviors:
            if not b.completed:
                pending.append(f"behavior '{b.name}'")
        for m in plan.metrics:
            if not m.completed:
                pending.append(f"metric '{m.name}'")
        for mp in plan.behavior_metric_mappings:
            if not mp.completed:
                pending.append(f"mapping '{mp.behavior}' → {', '.join(mp.metrics)}")

        if pending:
            return (
                "Cannot generate test sets yet. Complete these "
                "plan items first: " + "; ".join(pending) + "."
            )
        return None

    # ── tool execution ───────────────────────────────────────────

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Intercept internal tools, validate args, enforce constraints."""
        if tool_call.tool_name == InternalTool.SAVE_PLAN:
            return await self._execute_save_plan(tool_call)

        if tool_call.tool_name == InternalTool.AWAIT_TASK:
            return await self._execute_await_task(tool_call)

        error = self._check_plan_constraints(tool_call) or self._validate_tool_arguments(tool_call)
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
        if result.success:
            self._collect_id_names(result)
            self._collect_typed_entity_names(tool_call, result)
            self._record_link_if_mapping(tool_call)
            if self._plan:
                await self._track_plan_progress(tool_call, result)
        return result

    def _record_link_if_mapping(self, tool_call: ToolCall) -> None:
        """Capture (behavior, metric) pairs from successful ``add_behavior_to_metric`` calls.

        Recorded outside ``self._plan`` so links made BEFORE ``save_plan``
        is ever called still seed ``MappingSpec.completed`` when the plan
        is later saved (see ``_reconcile_plan_with_session_evidence``).

        Always stores the raw (behavior_id, metric_id) pair in
        ``_linked_id_pairs`` as a fallback for cases where the IDs weren't
        yet in ``_id_to_name`` at the time of the call (e.g. the plan's
        ``existing_id`` was used without a prior ``list_*`` call).
        """
        if tool_call.tool_name != "add_behavior_to_metric":
            return
        behavior_id = str(tool_call.arguments.get("behavior_id", ""))
        metric_id = str(tool_call.arguments.get("metric_id", ""))
        if behavior_id and metric_id:
            self._linked_id_pairs.add((behavior_id, metric_id))
        bname = self._id_to_name.get(behavior_id, "").lower()
        mname = self._id_to_name.get(metric_id, "").lower()
        if bname and mname:
            self._linked_pairs.add((bname, mname))

    # ── plan management ──────────────────────────────────────────

    async def _execute_save_plan(self, tool_call: ToolCall) -> ToolResult:
        """Parse LLM-provided plan data and store it."""
        return await self._execute_save_plan_body(tool_call)

    async def _execute_save_plan_body(self, tool_call: ToolCall) -> ToolResult:
        try:
            plan = ArchitectPlan.model_validate(_strip_llm_internal_fields(tool_call.arguments))
        except ValidationError as e:
            return self._save_plan_validation_failure(tool_call, e)
        except Exception as e:
            return self._save_plan_unexpected_failure(tool_call, e)

        # Seed both the global and type-scoped ID→name maps from any
        # (reuse) IDs the LLM included in the plan. Without this, reused
        # entities would only become known when the LLM later calls a
        # list_* tool — leaving the reconciliation check blind to them.
        for b in plan.behaviors:
            if b.existing_id and b.name:
                self._id_to_name[str(b.existing_id)] = b.name
                self._behavior_id_names[str(b.existing_id)] = b.name
        for m in plan.metrics:
            if m.existing_id and m.name:
                self._id_to_name[str(m.existing_id)] = m.name
                self._metric_id_names[str(m.existing_id)] = m.name

        self._reconcile_plan_with_session_evidence(plan)

        await self.set_mode_async(AgentMode.PLANNING)
        await self.set_plan_async(plan)
        logger.info(
            "[Architect] Plan saved: %d behaviors, %d test sets, %d metrics",
            len(plan.behaviors),
            len(plan.test_sets),
            len(plan.metrics),
        )
        project_label = f"{plan.project.name} — " if plan.project else ""
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

    def _reconcile_plan_with_session_evidence(self, plan: ArchitectPlan) -> None:
        """Mark plan items completed based on what we've actually observed this session.

        ``save_plan`` is regularly called *after* the LLM has already
        created behaviors, metrics, and behavior-metric links — for
        example, when the user iterates on the plan during execution
        ("also add a metric for X"). In that ordering, the entities
        exist on the platform but the LLM-supplied plan defaults every
        ``completed`` to False, which makes ``_check_execution_order``
        block ``generate_test_set`` indefinitely.

        We use the agent's own session evidence to recover:

        - ``self._behavior_id_names`` / ``self._metric_id_names`` are
          type-scoped maps populated only from behavior / metric tool
          results. Using these (rather than the global ``_id_to_name``)
          prevents false completions when an endpoint, project, or test
          set shares a name with a behavior or metric.
        - ``self._linked_pairs`` records every successful
          ``add_behavior_to_metric`` resolved to (behavior_name_lower,
          metric_name_lower). ``self._linked_id_pairs`` records the same
          links as raw (behavior_id, metric_id) pairs for cases where the
          IDs weren't yet in ``_id_to_name`` at link time.

        For behaviors/metrics: ``existing_id`` set OR ``reuse_status ==
        "reuse"`` OR a name match in the type-scoped map triggers
        completion. For mappings: all planned metrics must appear in
        either ``_linked_pairs`` (by name) or ``_linked_id_pairs`` (by
        ID, using ``existing_id`` from the plan items).
        """
        created_behavior_names = {v.lower() for v in self._behavior_id_names.values() if v}
        created_metric_names = {v.lower() for v in self._metric_id_names.values() if v}

        def _behavior_completed(name: str, existing_id: Optional[str]) -> bool:
            if existing_id:
                return True
            return bool(name) and name.lower() in created_behavior_names

        def _metric_completed(name: str, existing_id: Optional[str]) -> bool:
            if existing_id:
                return True
            return bool(name) and name.lower() in created_metric_names

        for b in plan.behaviors:
            if b.reuse_status == "reuse" or _behavior_completed(b.name, b.existing_id):
                b.completed = True
        for m in plan.metrics:
            if m.reuse_status == "reuse" or _metric_completed(m.name, m.existing_id):
                m.completed = True

        # Build a lookup from behavior/metric name to their existing_id so we
        # can check the raw ID-pair fallback for reused entities.
        behavior_name_to_id = {
            b.name.lower(): str(b.existing_id) for b in plan.behaviors if b.existing_id
        }
        metric_name_to_id = {
            m.name.lower(): str(m.existing_id) for m in plan.metrics if m.existing_id
        }

        def _metric_linked(bkey: str, mname: str) -> bool:
            if (bkey, mname) in self._linked_pairs:
                return True
            bid = behavior_name_to_id.get(bkey)
            mid = metric_name_to_id.get(mname)
            if bid and mid and (bid, mid) in self._linked_id_pairs:
                return True
            return False

        for mp in plan.behavior_metric_mappings:
            bkey = mp.behavior.lower()
            linked = [m for m in mp.metrics if _metric_linked(bkey, m.lower())]
            mp.linked_metrics = linked
            if mp.metrics and len(linked) == len(mp.metrics):
                mp.completed = True

    def _save_plan_failure(
        self, tool_call: ToolCall, error: Exception, *, error_text: str
    ) -> ToolResult:
        """Build a diagnostic ToolResult for any save_plan failure.

        Logs the offending arguments and returns a compact error
        string the LLM can act on directly.
        """
        logger.warning(
            "[Architect] save_plan failed (%s): %s | args: %s",
            type(error).__name__,
            error,
            self._preview_args(tool_call.arguments),
        )
        return ToolResult(
            tool_name=InternalTool.SAVE_PLAN,
            success=False,
            error=error_text,
        )

    def _save_plan_validation_failure(
        self, tool_call: ToolCall, error: "ValidationError"
    ) -> ToolResult:
        """Build a diagnostic ToolResult for a save_plan Pydantic ValidationError.

        The default ``str(ValidationError)`` is verbose and hard for an
        LLM to act on. We render a compact ``field: reason`` list so
        the model can immediately identify and fix the offending fields.
        """
        issues: List[str] = []
        for err in error.errors()[:10]:
            loc = ".".join(str(p) for p in err.get("loc", ()))
            msg = err.get("msg", "invalid value")
            issues.append(f"{loc}: {msg}" if loc else msg)
        if len(error.errors()) > 10:
            issues.append(f"... and {len(error.errors()) - 10} more")

        error_text = (
            "Plan validation failed:\n - "
            + "\n - ".join(issues)
            + "\nRe-call save_plan with corrected arguments. "
            "See save_plan instructions in the system prompt for allowed values."
        )
        return self._save_plan_failure(tool_call, error, error_text=error_text)

    def _save_plan_unexpected_failure(self, tool_call: ToolCall, error: Exception) -> ToolResult:
        """Fallback diagnostic for non-ValidationError failures during save_plan."""
        return self._save_plan_failure(
            tool_call,
            error,
            error_text=f"Could not save plan ({type(error).__name__}): {error}",
        )

    @staticmethod
    def _preview_args(args: Any, limit: int = 1500) -> str:
        """Render tool arguments as a truncated string for logging."""
        try:
            text = json.dumps(args, default=str)
        except (TypeError, ValueError):
            text = str(args)
        if len(text) > limit:
            return text[:limit] + f"... [{len(text) - limit} more chars]"
        return text

    # ── async task waiting ────────────────────────────────────────

    async def _execute_await_task(self, tool_call: ToolCall) -> ToolResult:
        """Pause the turn to wait for background tasks."""
        return self._execute_await_task_body(tool_call)

    def _execute_await_task_body(self, tool_call: ToolCall) -> ToolResult:
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

    async def _track_plan_progress(self, tool_call: ToolCall, result: ToolResult) -> None:
        """Mark plan items as completed after successful tool calls."""
        plan = self._plan
        if not plan:
            return

        category = plan_category_for(tool_call.tool_name)
        if not category:
            return

        name = (tool_call.arguments.get("name") or "").lower()
        updated = False

        if category == "project" and plan.project and not plan.project.completed:
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
            updated = self._match_mapping(plan, tool_call, self._id_to_name)

        if updated:
            await _emit(self._event_handlers, "on_plan_update", plan=plan)

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
                if not m.completed and m.name.lower() in prompt_lower:
                    m.completed = True
                    return True
        if name:
            for m in plan.metrics:
                if not m.completed and m.name.lower() == name:
                    m.completed = True
                    return True
        return False

    def _collect_id_names(self, result: ToolResult) -> None:
        """Extract id→name pairs from tool results for later lookup.

        Recognised payload shapes:
          - single object:                {"id": ..., "name": ...}
          - bare list:                    [{"id": ..., "name": ...}, ...]
          - MCP paginated list envelope:  {"results": [...], "_pagination": {...}}
          - legacy OData envelope:        {"value": [...]}
        """
        if not result.success or not result.content:
            return
        try:
            data = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return
        items, _ = _unwrap_list_envelope(data)
        if items is None:
            items = [data] if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict):
                eid = item.get("id")
                ename = item.get("name")
                if eid and ename:
                    self._id_to_name[str(eid)] = ename

    _BEHAVIOR_TOOLS: FrozenSet[str] = frozenset(
        {"create_behavior", "list_behaviors", "get_behavior"}
    )
    _METRIC_TOOLS: FrozenSet[str] = frozenset(
        {"create_metric", "list_metrics", "get_metric", "improve_metric", "generate_metric"}
    )

    def _collect_typed_entity_names(self, tool_call: ToolCall, result: ToolResult) -> None:
        """Populate type-scoped ID→name maps from behavior / metric tool results.

        Unlike the generic ``_collect_id_names``, this method scopes each ID
        to the entity type implied by the tool, preventing false completions
        in ``_reconcile_plan_with_session_evidence`` when a different entity
        type (endpoint, project, test set) happens to share the same name.
        """
        if not result.success or not result.content:
            return
        target: Optional[Dict[str, str]]
        if tool_call.tool_name in self._BEHAVIOR_TOOLS:
            target = self._behavior_id_names
        elif tool_call.tool_name in self._METRIC_TOOLS:
            target = self._metric_id_names
        else:
            return
        try:
            data = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return
        items, _ = _unwrap_list_envelope(data)
        if items is None:
            items = [data] if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict):
                eid = item.get("id")
                ename = item.get("name")
                if eid and ename:
                    target[str(eid)] = ename

    @staticmethod
    def _compact_list_result_for_history(
        content: str,
        max_items: int = 50,
        desc_chars: int = 80,
    ) -> Optional[str]:
        """Render a list/paginated-list tool result as a compact summary.

        The raw JSON of a 20-item ``list_metrics`` response easily exceeds
        the iteration-prompt char budget, which silently hides items from
        the LLM and makes it think entities don't exist. This renderer
        emits one line per item (id, name, short description, key
        attributes) so every item in the page is visible to the LLM in a
        fraction of the bytes.

        Returns ``None`` when ``content`` is not a recognised list shape,
        so callers can fall back to plain truncation.

        Recognised shapes:
          - bare list                     ``[{...}, ...]``
          - MCP paginated list envelope   ``{"results": [...], "_pagination": {...}}``
          - legacy OData envelope         ``{"value": [...]}``
        """
        if not content:
            return None
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None

        items, pagination = _unwrap_list_envelope(data)
        if items is None:
            return None
        if items and not all(isinstance(item, dict) for item in items):
            return None
        data = items

        lines: List[str] = []
        if pagination:
            returned = pagination.get("returned", len(data))
            has_more = bool(pagination.get("has_more"))
            header = f"List response: {returned} item(s) on this page"
            if has_more:
                next_skip = pagination.get("next_skip")
                header += (
                    f"; more pages available (next_skip={next_skip}). "
                    "Use $filter (e.g. $filter=tolower(name) eq 'x') to confirm a "
                    "specific name exists, or call again with the next skip."
                )
            else:
                header += " (no more pages)."
            lines.append(header)
        else:
            lines.append(f"List response: {len(data)} item(s)")

        if not data:
            return "\n".join(lines)

        shown = data[:max_items]
        for item in shown:
            name = item.get("name") or item.get("title") or "?"
            eid = item.get("id", "")
            desc = item.get("description") or item.get("summary") or ""
            if isinstance(desc, str) and len(desc) > desc_chars:
                desc = desc[:desc_chars].rstrip() + "…"
            extras: List[str] = []
            for key in ("score_type", "metric_scope", "behavior_type", "test_type"):
                val = item.get(key)
                if val not in (None, ""):
                    extras.append(f"{key}={val}")
            line = f"  - {name}"
            if eid:
                line += f" (id: {eid})"
            if extras:
                line += f" [{', '.join(extras)}]"
            if desc:
                line += f" — {desc}"
            lines.append(line)

        if len(data) > len(shown):
            lines.append(
                f"  … and {len(data) - len(shown)} more item(s) on this page (omitted from summary)"
            )

        return "\n".join(lines)

    @staticmethod
    def _match_mapping(
        plan: ArchitectPlan,
        tool_call: ToolCall,
        id_to_name: Dict[str, str],
    ) -> bool:
        """Record progress on a mapping after add_behavior_to_metric succeeds.

        Matches the call to a single mapping by BOTH behavior name AND
        a metric that is in that mapping's planned metrics list. The
        metric is appended to the mapping's ``linked_metrics`` and the
        mapping is marked ``completed`` only once every planned metric
        has been linked. This avoids the cross-mapping cascade that
        OR-based matching produces when metrics are shared across
        mappings (e.g. one metric covering several behaviors).
        """
        behavior_id = tool_call.arguments.get("behavior_id", "")
        metric_id = tool_call.arguments.get("metric_id", "")
        behavior = id_to_name.get(behavior_id, "").lower()
        metric = id_to_name.get(metric_id, "").lower()
        if not behavior or not metric:
            return False

        for mapping in plan.behavior_metric_mappings:
            if mapping.behavior.lower() != behavior:
                continue
            planned = next(
                (m for m in mapping.metrics if m.lower() == metric),
                None,
            )
            if planned is None:
                continue

            updated = False
            already_linked = {m.lower() for m in mapping.linked_metrics}
            if planned.lower() not in already_linked:
                mapping.linked_metrics.append(planned)
                updated = True

            if not mapping.completed:
                linked_lower = {m.lower() for m in mapping.linked_metrics}
                required_lower = {m.lower() for m in mapping.metrics}
                if required_lower and required_lower.issubset(linked_lower):
                    mapping.completed = True
                    updated = True
            return updated

        return False

    async def _apply_task_completions(self, message: str) -> None:
        """Parse a [TASK_COMPLETED] message and mark plan items done."""
        import re

        plan = self._plan
        if not plan:
            return

        updated = False
        for line in message.splitlines():
            match = re.search(r"Test set '([^']+)' generated successfully", line)
            if match:
                name = match.group(1).lower()
                for ts in plan.test_sets:
                    if not ts.completed and ts.name.lower() == name:
                        ts.completed = True
                        updated = True
                        break

        if updated:
            await _emit(self._event_handlers, "on_plan_update", plan=plan)

    # ── state serialisation ──────────────────────────────────────

    def dump_state(self) -> ArchitectAgentStateSnapshot:
        """Serialise all runtime state into a portable snapshot.

        The snapshot covers everything the backend needs to persist
        across Celery task boundaries and restore on the next turn.
        """
        plan_data: Optional[Dict[str, Any]] = None
        if self._plan:
            try:
                plan_data = self._plan.model_dump()
            except Exception:
                logger.warning("Failed to serialise agent plan", exc_info=True)

        return ArchitectAgentStateSnapshot(
            mode=self._mode.value if hasattr(self._mode, "value") else str(self._mode),
            workflow_path=self._workflow_path.value,
            conversation_history=list(self._conversation_history),
            discovery_state=dict(self._discovery_state),
            guard_state=self.guard_state,
            id_to_name=dict(self._id_to_name),
            plan_data=plan_data,
            max_iterations=self.max_iterations,
            pending_tasks=list(self._pending_tasks),
        )

    def restore_state(self, snapshot: ArchitectAgentStateSnapshot) -> None:
        """Restore agent state from a snapshot produced by ``dump_state``.

        Unknown mode values fall back to DISCOVERY with a warning so a
        bad DB value never silently corrupts the agent.  Plan restore
        failures are also logged with the full traceback.
        """
        try:
            self._mode = AgentMode(snapshot.mode)
        except ValueError:
            logger.warning(
                "Unknown agent mode %r in snapshot, defaulting to DISCOVERY",
                snapshot.mode,
            )
            self._mode = AgentMode.DISCOVERY

        try:
            self._workflow_path = WorkflowPath(snapshot.workflow_path)
        except ValueError:
            self._workflow_path = WorkflowPath.UNSET

        self._conversation_history = list(snapshot.conversation_history)

        if snapshot.discovery_state:
            self._discovery_state = snapshot.discovery_state

        if snapshot.guard_state:
            self.guard_state = snapshot.guard_state

        if snapshot.id_to_name:
            self._id_to_name = dict(snapshot.id_to_name)

        if snapshot.plan_data:
            try:
                self._plan = ArchitectPlan.model_validate(snapshot.plan_data)
            except Exception:
                logger.warning("Failed to restore plan from snapshot", exc_info=True)

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

    def _format_plan_progress(self) -> str:
        """Render a one-line summary of plan completion per category.

        Surfaces what's blocking ordering-sensitive tools (most notably
        ``generate_test_set`` and ``create_test_set_bulk``, which require
        every behavior, metric, and mapping to be completed). Showing the
        progress directly in the iteration prompt lets the LLM reason
        about ordering on its own instead of relying on hidden runtime
        gating.
        """
        plan = self._plan
        if not plan:
            return ""

        def _ratio(items: list) -> str:
            total = len(items)
            done = sum(1 for it in items if getattr(it, "completed", False))
            return f"{done}/{total}"

        parts = [
            f"behaviors {_ratio(plan.behaviors)}",
            f"metrics {_ratio(plan.metrics)}",
            f"mappings {_ratio(plan.behavior_metric_mappings)}",
            f"test_sets {_ratio(plan.test_sets)}",
        ]

        # "ready" requires all three prerequisite sections to be non-empty
        # AND fully completed — an empty plan trivially satisfies all([]),
        # which would misleadingly surface "ready" before anything is planned.
        prereqs_complete = (
            bool(plan.behaviors)
            and bool(plan.metrics)
            and all(b.completed for b in plan.behaviors)
            and all(m.completed for m in plan.metrics)
            and all(mp.completed for mp in plan.behavior_metric_mappings)
        )
        gate = (
            "test-set generation: ready"
            if prereqs_complete
            else "test-set generation: blocked until behaviors, metrics, and mappings reach N/N"
        )

        return "Plan progress: " + ", ".join(parts) + ". " + gate + "."

    def _maybe_update_workflow_path(self, message: str) -> None:
        """Infer or update workflow path from user signals."""
        has_attachments = bool(self._attachments)
        updated = resolve_workflow_path_update(
            self._workflow_path, message, has_attachments=has_attachments
        )
        if updated is not None:
            self._workflow_path = updated

    def _build_prompt(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
    ) -> str:
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history()
        plan_text = self._plan.to_markdown() if self._plan else ""
        plan_progress_text = self._format_plan_progress()
        discovery_text = self._format_discovery_state()
        attachments_text = self._format_attachments()

        template = self._jinja_env.get_template("iteration_prompt.j2")
        phase_knowledge_text = render_phase_knowledge(
            self._jinja_env, self._mode, self._workflow_path
        )
        return template.render(
            mode=self._mode,
            workflow_path=self._workflow_path.value,
            phase_knowledge_text=phase_knowledge_text,
            user_query=user_query,
            tools_text=tools_text,
            history_text=history_text,
            plan_text=plan_text,
            plan_progress_text=plan_progress_text,
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
            parts.append(f"Endpoint: {ds['endpoint_name']} (id: {ds['endpoint_id']})")
        parts.append("Explored: yes" if ds.get("explored") else "Explored: not yet")
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
                parts.append(f"  - @{m['type']}:{m['display']} (id: {m['id']})")

        files = self._attachments.get("files")
        if files:
            for f in files:
                filename = f.get("filename", "unknown")
                # Prefer ``extracted_text`` (the canonical key across the rest
                # of the pipeline); fall back to ``content`` for any
                # in-flight payloads still using the legacy key.
                content = f.get("extracted_text") or f.get("content") or ""
                if len(content) > cfg.max_attachment_chars:
                    content = content[: cfg.max_attachment_chars] + "\n\n[... truncated ...]"
                parts.append(f"Attached file: {filename}\n```\n{content}\n```")

        return "\n".join(parts)

    # ── streaming finish (Phase 2 LLM call) ──────────────────────

    async def _handle_finish_action(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Stream the final response token-by-token."""
        logger.info("[Architect] Streaming final response")
        # Derive confirmation from runtime state — never from
        # ``action.needs_confirmation``. The Accept/Change UI is only
        # meaningful when **this turn** intercepted a confirmable tool
        # call. That signal is ``self._blocked_this_turn``, set inside
        # ``_handle_tool_calls`` whenever the LLM tries to call a tool
        # flagged ``requires_confirmation: true`` in ``mcp_tools.yaml``
        # without prior approval. We deliberately do NOT key off
        # ``_confirming_tools``: that set persists across turns as a
        # long-lived approval scope, so reading it here would surface
        # spurious Accept/Change prompts on later turns (for example,
        # the auto-resumed [TASK_COMPLETED] summary that follows an
        # already-approved exploration).
        confirmation = self._blocked_this_turn and not self._auto_approve_all
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
        conv_window = self._conversation_history[-self._history_window :]
        plan_text = self._plan.to_markdown() if self._plan else ""
        tool_results_text = self._format_tool_results_for_streaming()

        template = self._jinja_env.get_template("streaming_response.j2")
        return template.render(
            conversation_history=conv_window,
            plan_text=plan_text,
            tool_results=tool_results_text,
            reasoning=reasoning,
            final_answer=final_answer,
        )

    def _render_tool_result(self, tr: ToolResult, *, prefix: str, preview: int) -> Optional[str]:
        """Render a single ToolResult as a compact string for history/streaming prompts.

        Returns ``None`` when the result carries nothing worth including
        (no content and no error).
        """
        if tr.success and tr.content:
            compact = self._compact_list_result_for_history(tr.content)
            if compact is not None:
                return f"{prefix}:\n{compact}"
            return f"{prefix}: {tr.content[:preview]}"
        if tr.error:
            return f"{prefix} Error: {tr.error}"
        return None

    def _format_tool_results_for_streaming(self) -> str:
        """Format tool results from the current turn."""
        if not self._execution_history:
            return ""
        cfg = self._cfg
        parts: List[str] = []
        for step in self._execution_history:
            if step.tool_results:
                for tr in step.tool_results:
                    rendered = self._render_tool_result(
                        tr,
                        prefix=f"[{tr.tool_name}]",
                        preview=cfg.tool_result_preview_chars,
                    )
                    if rendered:
                        parts.append(rendered)
        return "\n\n".join(parts)

    # ── history formatting ───────────────────────────────────────

    def _format_history(self) -> str:
        parts: List[str] = []
        cfg = self._cfg

        conv_window = self._conversation_history[-self._history_window :]
        if len(self._conversation_history) > self._history_window:
            omitted = len(self._conversation_history) - self._history_window
            parts.append(f"[... {omitted} earlier messages omitted ...]")

        recent_start = max(0, len(conv_window) - cfg.recent_msg_limit)
        for i, msg in enumerate(conv_window):
            role = msg["role"].capitalize()
            content = msg["content"]
            max_chars = cfg.recent_msg_max_chars if i >= recent_start else cfg.older_msg_max_chars
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
            parts.append(f"{role}: {content}")

        exec_window = self._execution_history[-self._history_window :]
        if len(self._execution_history) > self._history_window:
            omitted = len(self._execution_history) - self._history_window
            parts.append(f"[... {omitted} earlier tool steps omitted ...]")
        for step in exec_window:
            reasoning_preview = step.reasoning[: cfg.reasoning_preview_chars]
            parts.append(f"[Tool iteration {step.iteration}] Reasoning: {reasoning_preview}")
            if step.tool_calls:
                for tc in step.tool_calls:
                    parts.append(f"  Called: {tc.tool_name}")
            if step.tool_results:
                for tr in step.tool_results:
                    rendered = self._render_tool_result(
                        tr,
                        prefix=f"  Result ({tr.tool_name})",
                        preview=cfg.tool_result_preview_chars,
                    )
                    if rendered:
                        parts.append(rendered)

        return "\n".join(parts) if parts else ""

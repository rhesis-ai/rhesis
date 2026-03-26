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
from rhesis.sdk.agents.constants import Action, InternalTool, Role, ToolMeta
from rhesis.sdk.agents.events import AgentEventHandler, _emit
from rhesis.sdk.agents.schemas import AgentAction, ExecutionStep, ToolCall, ToolResult
from rhesis.sdk.models.base import BaseLLM

from .plan import ArchitectPlan

logger = logging.getLogger(__name__)

# HTTP methods that are considered read-only.  Used as a fallback
# when a tool definition lacks an explicit ``requires_confirmation``
# flag — tools whose HTTP method is not in this set are treated as
# requiring confirmation.
_READONLY_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


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

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        tools: Optional[List[Union[BaseTool, MCPTool]]] = None,
        max_iterations: int = 15,
        max_tool_executions: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        history_window: Optional[int] = None,
        verbose: bool = False,
        event_handlers: Optional[List[AgentEventHandler]] = None,
    ):
        super().__init__(
            model=model,
            tools=tools,
            max_iterations=max_iterations,
            max_tool_executions=max_tool_executions,
            timeout_seconds=timeout_seconds,
            history_window=history_window,
            verbose=verbose,
            event_handlers=event_handlers,
            prompt_templates_dir=(Path(__file__).parent / "prompt_templates"),
        )
        self._conversation_history: List[Dict[str, Any]] = []
        self._plan: Optional[ArchitectPlan] = None
        self._mode: str = "discovery"

        # ── write-guard state ────────────────────────────────────
        # Two-layer defense:
        #  Layer 1 (prompt): The system prompt tells the LLM to present
        #    a plan and ask for confirmation before creating entities.
        #  Layer 2 (structural): This guard intercepts mutating tool
        #    calls if the LLM ignores the prompt.  It is a safety net,
        #    not a replacement for prompt-based control.
        #
        # _confirming_tools: the specific tools that were blocked and
        #   presented for confirmation.  Only these are unlocked when
        #   the user replies — not all mutating tools.
        # _creation_approved: True for the turn immediately after a
        #   confirmation prompt, False otherwise.
        # _mutating_tools: lazily built from tool metadata on first
        #   call to get_available_tools().
        self._creation_approved: bool = False
        self._confirming_tools: FrozenSet[str] = frozenset()
        self._mutating_tools: Optional[FrozenSet[str]] = None
        self._auto_approve_all: bool = False

        # ── discovery state ───────────────────────────────────────
        self._discovery_state: Dict[str, Any] = {
            "endpoint_id": None,
            "endpoint_name": None,
            "explored": False,
            "observations": [],
            "user_confirmed_areas": [],
            "open_questions": [],
        }

        # ── per-turn attachments (mentions + file text) ──────────
        self._attachments: Optional[Dict[str, Any]] = None

    # ── public API ──────────────────────────────────────────────────

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
            self._conversation_history.append({"role": Role.USER, "content": message})

            # If the previous turn asked for confirmation, unlock
            # only the specific tools that were blocked — not all
            # mutating tools.  The LLM decides whether the user's
            # message is an approval or a change request; the guard
            # just ensures at least one confirmation round-trip
            # happened before any write operation.
            if self._needs_confirmation and self._confirming_tools:
                self._creation_approved = True

            if self.verbose:
                print(f"\n[Architect:{self._mode}] User: {message}")

            await _emit(
                self._event_handlers,
                "on_agent_start",
                query=message,
            )

            try:
                response = await self._run_loop(message)

                self._conversation_history.append({"role": Role.ASSISTANT, "content": response})

                # Reset per-turn state — approval and attachments
                # are valid for a single turn only.
                self._creation_approved = False
                self._attachments = None

                if self.verbose:
                    print(f"[Architect:{self._mode}] Response: {response[:200]}...")

                return response
            finally:
                await self._disconnect_tools()

    @property
    def plan(self) -> Optional[ArchitectPlan]:
        """The current plan, if one has been produced."""
        return self._plan

    @plan.setter
    def plan(self, value: ArchitectPlan) -> None:
        """Set the plan and emit a plan_update event."""
        self._plan = value

    async def set_plan_async(self, value: ArchitectPlan) -> None:
        """Set the plan and emit a plan_update event (async)."""
        self._plan = value
        await _emit(self._event_handlers, "on_plan_update", plan=value)

    @property
    def mode(self) -> str:
        """Current agent mode."""
        return self._mode

    async def set_mode_async(self, new_mode: str) -> None:
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
    def discovery_state(self) -> Dict[str, Any]:
        """Current discovery state (what the agent knows and needs to learn)."""
        return self._discovery_state

    @discovery_state.setter
    def discovery_state(self, value: Dict[str, Any]) -> None:
        self._discovery_state = value

    @property
    def auto_approve_all(self) -> bool:
        """Whether all mutating tools are auto-approved (no confirmation)."""
        return self._auto_approve_all

    @auto_approve_all.setter
    def auto_approve_all(self, value: bool) -> None:
        self._auto_approve_all = value

    @property
    def guard_state(self) -> Dict[str, Any]:
        """Current state of the write-guard (confirmation flow)."""
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
        self._mode = "discovery"
        self._creation_approved = False
        self._confirming_tools = frozenset()
        self._mutating_tools = None
        self._auto_approve_all = False
        self._attachments = None
        self._discovery_state = {
            "endpoint_id": None,
            "endpoint_name": None,
            "explored": False,
            "observations": [],
            "user_confirmed_areas": [],
            "open_questions": [],
        }

    # ── write-guard ────────────────────────────────────────────────

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Override to discover which tools require confirmation.

        Classification priority:
        1. Explicit ``requires_confirmation`` flag (from YAML / MCP annotations)
        2. MCP ``readOnlyHint`` annotation — if True the tool is read-only
        3. MCP ``destructiveHint`` annotation — if True the tool is mutating
        4. ``http_method`` (set by LocalToolProvider) — GET/HEAD/OPTIONS are
           read-only, everything else requires confirmation
        """
        tools = await super().get_available_tools()

        if self._mutating_tools is None:
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
                    if method not in _READONLY_HTTP_METHODS:
                        mutating.add(t["name"])
            self._mutating_tools = frozenset(mutating)
            logger.debug(
                "[Architect] Discovered %d tools requiring confirmation: %s",
                len(self._mutating_tools),
                sorted(self._mutating_tools),
            )
        return tools

    def _is_mutating(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation before execution."""
        if self._mutating_tools is None:
            # Tools not yet discovered — be conservative
            return True
        return tool_name in self._mutating_tools

    async def _handle_tool_calls(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Override to block mutating tools until the user confirms.

        If the LLM tries to call a tool that requires confirmation
        without prior user approval, the call is intercepted and
        converted into a finish action that presents the plan and
        asks for confirmation.  Read-only tools are always allowed.

        When ``auto_approve_all`` is set, all tools are allowed
        without confirmation (session-level override).

        When a block occurs, ALL mutating tools are placed in the
        confirming set so that the user's approval covers the full
        plan — not just the first batch of blocked tools.
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

            # Unlock ALL mutating tools on approval so the full plan
            # can execute without re-blocking on subsequent tool types.
            self._confirming_tools = self._mutating_tools or frozenset(blocked_names)

            # Allow read-only tools to still execute (e.g. list_metrics
            # called alongside create_metric)
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

            # Convert to a finish action that asks for confirmation
            finish_action = AgentAction(
                reasoning=(
                    f"{action.reasoning}\n\n"
                    f"[BLOCKED] The following tools require user "
                    f"confirmation: {blocked_names}. "
                    f"Present the plan and ask the user to confirm."
                ),
                action=Action.FINISH,
                final_answer=action.final_answer or action.reasoning,
                needs_confirmation=True,
            )
            return await self._handle_finish_action(finish_action, iteration)

        # No mutating tools, or approved — proceed normally
        return await super()._handle_tool_calls(action, iteration)

    def _is_approved(self, tool_calls: list) -> bool:
        """Check if the requested tool calls are approved.

        Returns True if session-level auto-approve is on, or if
        the user approved and the requested tools are in the
        confirming set (which now includes all mutating tools
        after any plan-level approval).
        """
        if self._auto_approve_all:
            return True
        if not self._creation_approved:
            return False
        return all(tc.tool_name in self._confirming_tools for tc in tool_calls)

    # ── argument validation (structural defense) ───────────────────

    MAX_PAYLOAD_BYTES = 100_000  # 100 KB per tool call
    MAX_STRING_VALUE_LEN = 10_000  # 10 KB per individual string value
    MAX_ARRAY_ITEMS = 100  # max items in any single array argument

    def _validate_tool_arguments(self, tool_call: ToolCall) -> Optional[str]:
        """Validate tool arguments before execution.

        Returns an error message if validation fails, None if ok.
        This is a structural defense — prevents oversized payloads,
        excessively long strings, and unreasonable array sizes
        regardless of what the LLM generates.
        """
        args = tool_call.arguments
        try:
            serialized = json.dumps(args, default=str)
        except (TypeError, ValueError):
            return "Tool arguments could not be serialized"

        if len(serialized.encode("utf-8")) > self.MAX_PAYLOAD_BYTES:
            return (
                f"Tool arguments exceed the {self.MAX_PAYLOAD_BYTES // 1000} KB "
                f"payload limit. Break the operation into smaller calls."
            )

        for key, value in args.items():
            if isinstance(value, str) and len(value) > self.MAX_STRING_VALUE_LEN:
                return (
                    f"Argument '{key}' exceeds the "
                    f"{self.MAX_STRING_VALUE_LEN // 1000} KB string limit."
                )
            if isinstance(value, list) and len(value) > self.MAX_ARRAY_ITEMS:
                return (
                    f"Argument '{key}' contains {len(value)} items "
                    f"(max {self.MAX_ARRAY_ITEMS}). Split into multiple calls."
                )

        return None

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Override to validate arguments before execution."""
        error = self._validate_tool_arguments(tool_call)
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
        return await super().execute_tool(tool_call)

    # ── transport lifecycle ─────────────────────────────────────────

    async def _disconnect_tools(self) -> None:
        """Disconnect all MCP tool transports.

        Called at the end of each ``chat_async()`` turn so that the
        transport's async generators are properly closed before
        ``asyncio.run()`` destroys the event loop. The auto-reconnect
        in ``MCPTool._ensure_connected()`` handles the next call.
        """
        for tool in self._tools:
            if isinstance(tool, MCPTool):
                try:
                    await tool.disconnect()
                except Exception:
                    pass

    # ── prompt building (overrides) ────────────────────────────────

    def _build_prompt(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
    ) -> str:
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history()
        plan_text = self._plan.to_markdown() if self._plan else ""
        discovery_state_text = self._format_discovery_state()
        attachments_text = self._format_attachments()

        template = self._jinja_env.get_template("iteration_prompt.j2")
        return template.render(
            mode=self._mode,
            user_query=user_query,
            tools_text=tools_text,
            history_text=history_text,
            plan_text=plan_text,
            discovery_state_text=discovery_state_text,
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
        if ds.get("explored"):
            parts.append("Explored: yes")
        else:
            parts.append("Explored: not yet")
        if ds.get("observations"):
            parts.append("Observations:")
            for obs in ds["observations"]:
                parts.append(f"  - {obs}")
        if ds.get("user_confirmed_areas"):
            parts.append("User-confirmed testing areas:")
            for area in ds["user_confirmed_areas"]:
                parts.append(f"  - {area}")
        if ds.get("open_questions"):
            parts.append("Open questions:")
            for q in ds["open_questions"]:
                parts.append(f"  - {q}")
        return "\n".join(parts)

    # ── attachment formatting ────────────────────────────────────

    def _format_attachments(self) -> str:
        """Format per-turn attachments (mentions and files) for the prompt."""
        if not self._attachments:
            return ""

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
                content = f.get("content", "")
                if len(content) > 20000:
                    content = content[:20000] + "\n\n[... truncated ...]"
                parts.append(f"Attached file: {filename}\n```\n{content}\n```")

        return "\n".join(parts)

    # ── streaming finish (Phase 2 LLM call) ─────────────────────

    async def _handle_finish_action(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Override to stream the final response token-by-token."""
        logger.info("[Architect] Streaming final response")
        self._needs_confirmation = action.needs_confirmation

        seed = action.final_answer or ""
        streaming_prompt = self._build_streaming_prompt(
            reasoning=action.reasoning,
            final_answer=seed,
        )

        streamed_content = await self._stream_final_response(
            prompt=streaming_prompt,
            system_prompt="",
            fallback_content=seed,
            needs_confirmation=action.needs_confirmation,
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

        # Include tool results so the LLM can reference actual data
        tool_results_text = self._format_tool_results_for_streaming()

        template = self._jinja_env.get_template("streaming_response.j2")
        return template.render(
            conversation_history=conv_window,
            plan_text=plan_text,
            tool_results=tool_results_text,
            reasoning=reasoning,
            final_answer=final_answer,
        )

    def _format_tool_results_for_streaming(self) -> str:
        """Format tool results from the current turn for the streaming prompt."""
        if not self._execution_history:
            return ""
        parts: List[str] = []
        for step in self._execution_history:
            if step.tool_results:
                for tr in step.tool_results:
                    if tr.success and tr.content:
                        parts.append(f"[{tr.tool_name}]: {tr.content[:4000]}")
                    elif tr.error:
                        parts.append(f"[{tr.tool_name}] Error: {tr.error}")
        return "\n\n".join(parts)

    # ── history formatting ─────────────────────────────────────────

    def _format_history(self) -> str:
        parts: List[str] = []

        # Conversation history -- windowed
        conv_window = self._conversation_history[-self._history_window :]
        if len(self._conversation_history) > self._history_window:
            omitted = len(self._conversation_history) - self._history_window
            parts.append(f"[... {omitted} earlier messages omitted ...]")
        for msg in conv_window:
            role = msg["role"].capitalize()
            content = msg["content"]
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"{role}: {content}")

        # Execution history -- windowed
        exec_window = self._execution_history[-self._history_window :]
        if len(self._execution_history) > self._history_window:
            omitted = len(self._execution_history) - self._history_window
            parts.append(f"[... {omitted} earlier tool steps omitted ...]")
        for step in exec_window:
            parts.append(f"[Tool iteration {step.iteration}] Reasoning: {step.reasoning[:200]}")
            if step.tool_calls:
                for tc in step.tool_calls:
                    parts.append(f"  Called: {tc.tool_name}")
            if step.tool_results:
                for tr in step.tool_results:
                    if tr.success:
                        content_preview = tr.content[:4000]
                        parts.append(f"  Result ({tr.tool_name}): {content_preview}")
                    else:
                        parts.append(f"  Error ({tr.tool_name}): {tr.error}")

        return "\n".join(parts) if parts else ""

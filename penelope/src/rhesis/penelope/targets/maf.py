"""
Microsoft Agent Framework (MAF) target implementation for Penelope.

Wraps any MAF agent (``agent-framework`` Python package)
so it can be driven by Penelope's autonomous, multi-turn testing agent.

MAF agents expose an *async* ``run`` method while Penelope's :class:`Target`
contract is *synchronous*, and MAF tracks multi-turn state in a thread/session
*object* while Penelope passes it around as a *string* ``conversation_id``.  This
adapter bridges both gaps:

1. Async <-> sync: the real interaction lives in :meth:`a_send_message`; the sync
   :meth:`send_message` drives it, correctly handling the case where an event loop
   is already running.
2. ``conversation_id`` <-> thread object: an internal ``dict[str, AgentThread]``
   registry maps the stable string id Penelope uses to the MAF thread/session
   object that actually holds the conversation context.

The ``agent-framework`` package is intentionally **not** imported at module load
time; the adapter only duck-types the agent object, so importing this module never
hard-requires the dependency.  MAF API names differ between versions: current builds
expose ``Agent`` / ``create_session()`` / ``run(session=...)`` while older builds
expose ``ChatAgent`` / ``get_new_thread()`` / ``run(thread=...)``.  The helpers below
try the current names first and fall back to the legacy ones, always passing the
conversation-state object under the keyword that matches the factory that produced
it.

Usage::

    >>> from agent_framework import Agent
    >>> from agent_framework.openai import OpenAIChatClient
    >>>
    >>> agent = Agent(client=OpenAIChatClient(), instructions="You are helpful.")
    >>> target = MAFTarget(agent, "maf-bot", "My MAF agent")
    >>> response = target.send_message("Hello!")
    >>> follow_up = target.send_message("And again?", response.conversation_id)
"""

import asyncio
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Dict, List, Optional, Tuple
from uuid import uuid4

from rhesis.sdk.targets import Target, TargetResponse

# Candidate factory methods used to mint a fresh conversation thread/session,
# in priority order.  Different MAF versions name this differently; the current
# ``create_session`` API is tried before the legacy ``get_new_thread`` one.
_THREAD_FACTORY_METHODS: Tuple[str, ...] = (
    "create_session",
    "get_new_session",
    "get_new_thread",
    "new_thread",
)

# Candidate keyword names under which the thread/session object is passed to
# ``agent.run(...)``, in priority order (current ``session`` before legacy
# ``thread``).
_THREAD_RUN_KWARGS: Tuple[str, ...] = ("session", "thread")

# Maps each thread/session factory method to the ``run`` kwarg it expects.
_FACTORY_TO_RUN_KWARG: Dict[str, str] = {
    "create_session": "session",
    "get_new_session": "session",
    "get_new_thread": "thread",
    "new_thread": "thread",
}


def _json_safe(value: Any) -> Any:
    """
    Coerce a MAF framework object into something ``json.dumps`` can serialize.

    Response metadata (e.g. ``usage`` / ``usage_details``) is placed into the
    :class:`TargetResponse` metadata dict, which Penelope's executor serializes
    with ``json.dumps`` *without* a fallback encoder.  Real MAF responses expose
    these as framework objects (not plain dicts), so they must be reduced to JSON
    primitives here to avoid a ``TypeError`` that the target cannot catch.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_safe(model_dump(mode="json"))
        except Exception:
            try:
                return _json_safe(model_dump())
            except Exception:
                pass
    return str(value)


class MAFTarget(Target):
    """
    Target for MAF (Microsoft Agent Framework) agents.

    Works with any MAF agent (``ChatAgent``, ``Agent``, ``AIAgent`` or anything
    implementing the framework's async ``run`` method).  Multi-turn context is
    preserved by keeping a per-conversation thread/session object keyed by the
    string ``conversation_id`` that Penelope threads through each turn.
    """

    def __init__(
        self,
        agent: Any,
        target_id: str,
        description: Optional[str] = None,
    ):
        """
        Initialize the MAF target.

        Args:
            agent: Any MAF agent exposing an async ``run`` method.
            target_id: Unique identifier for this target.
            description: Human-readable description of what this target does.
        """
        self.agent = agent
        self._target_id = target_id
        self._description = description or (
            f"MAF {type(agent).__name__}: {target_id}"
        )

        # Registry mapping the string conversation_id Penelope uses to the MAF
        # thread/session object that holds that conversation's context.
        self._threads: Dict[str, Any] = {}

        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid MAF target: {error}")

    @property
    def target_type(self) -> str:
        return "maf"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate the MAF target configuration."""
        if self.agent is None:
            return False, "Agent cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        # MAF's ``run`` is async, but across versions it is exposed either as a
        # coroutine function or as an overloaded function returning an awaitable,
        # so the only reliable check is that ``run`` is callable.
        if not callable(getattr(self.agent, "run", None)):
            return False, "Agent must have a callable async run() method"
        return True, None

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Send a message to the MAF agent (synchronous entry point).

        This simply drives the async :meth:`a_send_message`; all real logic lives
        there so both sync and native-async callers share one code path.
        """
        return self._run_coroutine(
            self.a_send_message(message, conversation_id, files=files, **kwargs)
        )

    async def a_send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Send a message to the MAF agent (native async entry point).

        Penelope's executor awaits this directly, so the real interaction is
        implemented here.  Any exception is converted into an unsuccessful
        :class:`TargetResponse`; this method never raises.

        Note:
            ``files`` is accepted for interface compatibility but ignored: the MAF
            agents in scope here are plain conversational agents that do not accept
            attachments.  Forward attachments via the agent construction instead.
        """
        if not message or not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            thread, resolved_id = await self._resolve_thread(conversation_id)
            response = await self._run_agent(message, thread)
            content = self._extract_text(response)

            return TargetResponse(
                success=True,
                content=content,
                conversation_id=resolved_id,
                metadata=self._build_metadata(message, response),
            )
        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"MAF error: {e}",
            )

    async def _resolve_thread(self, conversation_id: Optional[str]) -> Tuple[Any, str]:
        """
        Resolve the MAF thread/session object for a conversation.

        - First turn (``conversation_id is None``): generate a fresh id, create a
          new thread, register it, and return both.
        - Subsequent turns: reuse the registered thread so context is preserved.
        - Unknown id: create a fresh thread for it (so a caller-supplied id still
          works without an error).
        """
        if conversation_id is None:
            conversation_id = uuid4().hex
            self._threads[conversation_id] = await self._create_thread()
        elif conversation_id not in self._threads:
            self._threads[conversation_id] = await self._create_thread()

        return self._threads[conversation_id], conversation_id

    async def _create_thread(self) -> Any:
        """
        Create a new MAF thread/session via whichever factory the agent exposes.

        Returns ``None`` when the agent provides no thread factory (a stateless
        agent); the conversation_id remains stable regardless, but per-turn
        context will only persist if the agent itself supports threads/sessions.
        """
        method_name = self._state_factory_method()
        if method_name is None:
            return None
        factory = getattr(self.agent, method_name)
        result = factory()
        if inspect.isawaitable(result):
            result = await result
        return result

    def _state_factory_method(self) -> Optional[str]:
        """Return the name of the first thread/session factory the agent exposes."""
        for method_name in _THREAD_FACTORY_METHODS:
            if callable(getattr(self.agent, method_name, None)):
                return method_name
        return None

    def is_stateful(self) -> bool:
        """Whether the agent exposes a thread/session factory for multi-turn memory."""
        return self._state_factory_method() is not None

    async def _run_agent(self, message: str, thread: Any) -> Any:
        """Invoke the agent's async ``run`` with the right thread/session kwarg."""
        run_kwargs: Dict[str, Any] = {}
        if thread is not None:
            kwarg_name = self._thread_run_kwarg()
            if kwarg_name is not None:
                run_kwargs[kwarg_name] = thread

        result = self.agent.run(message, **run_kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _thread_run_kwarg(self) -> Optional[str]:
        """
        Pick the keyword (``session`` vs ``thread``) under which to pass state to ``run``.

        The kwarg is derived from the factory that produced the state object so it
        always matches what :meth:`_create_thread` built, then validated against
        ``run``'s real signature.  This keeps object creation and invocation in
        lock-step: an agent whose ``create_session`` minted a *session* never has
        that object passed under ``thread=`` (which ``run`` would drop into
        ``**kwargs`` and silently ignore, losing conversation memory).
        """
        preferred = self._state_kwarg_from_factory()
        try:
            params = inspect.signature(self.agent.run).parameters
        except (TypeError, ValueError):
            # Signature unavailable (e.g. C-implemented); trust the factory kwarg.
            return preferred or _THREAD_RUN_KWARGS[0]

        accepts_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )

        # Prefer the factory-matched kwarg whenever ``run`` can receive it, either
        # as an explicit parameter or via ``**kwargs``.
        if preferred and (preferred in params or accepts_var_keyword):
            return preferred

        # Otherwise fall back to whatever named state kwarg ``run`` actually exposes.
        for name in _THREAD_RUN_KWARGS:
            if name in params:
                return name

        # No named state kwarg; only pass one if ``run`` accepts ``**kwargs``.
        if accepts_var_keyword:
            return preferred or _THREAD_RUN_KWARGS[0]
        return None

    def _state_kwarg_from_factory(self) -> Optional[str]:
        """Return the ``run`` kwarg that matches the agent's thread/session factory."""
        method_name = self._state_factory_method()
        if method_name is None:
            return None
        return _FACTORY_TO_RUN_KWARG[method_name]

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Read the assistant text off a MAF run response (e.g. ``.text``)."""
        text = getattr(response, "text", None)
        if text is None:
            return str(response)
        return str(text)

    def _build_metadata(self, message: str, response: Any) -> Dict[str, Any]:
        """Collect useful, best-effort detail without crashing on missing fields."""
        metadata: Dict[str, Any] = {
            "input_sent": message,
            "agent_type": type(self.agent).__name__,
            "raw_response": repr(response),
        }
        for field in ("response_id", "usage", "usage_details"):
            value = getattr(response, field, None)
            if value is not None:
                metadata[field] = _json_safe(value)
        return metadata

    @staticmethod
    def _run_coroutine(coro: Awaitable[Any]) -> Any:
        """
        Run an awaitable to completion from synchronous code.

        Uses :func:`asyncio.run` when no event loop is active.  If a loop is
        already running in this thread (e.g. inside a notebook or an async host),
        ``asyncio.run`` would raise, so the coroutine is executed in a dedicated
        worker thread with its own event loop instead.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()

    def get_tool_documentation(self) -> str:
        """Get documentation for Penelope."""
        if self.is_stateful():
            memory = "Yes (stateful agent with conversation history via thread/session)"
            continuity = (
                "Maintain conversation_id for conversation continuity across multiple turns.\n"
                "The agent maintains full conversation context automatically for a given\n"
                "conversation_id; the first turn returns a new conversation_id to reuse."
            )
        else:
            memory = "No (stateless agent; each turn is independent)"
            continuity = (
                "This agent exposes no thread/session factory, so each message is\n"
                "independent. A conversation_id is still returned for tracking, but it\n"
                "does not restore prior context."
            )
        return f"""
Target: {self._description}
Type: MAF {type(self.agent).__name__}
Memory: {memory}

Send messages using send_message_to_target(message, conversation_id).
{continuity}
"""

    def clear_session(self, conversation_id: str) -> None:
        """
        Forget the thread/session for a conversation.

        Args:
            conversation_id: The conversation to clear.
        """
        self._threads.pop(conversation_id, None)

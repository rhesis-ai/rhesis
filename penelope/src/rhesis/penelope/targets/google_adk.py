"""
Google ADK target implementation for Penelope.

Wraps a Google ADK ``Runner`` -- or a bare ADK agent, which the adapter wraps in
a ``Runner`` itself -- so it can be driven by Penelope's autonomous, multi-turn
testing agent.

Three gaps have to be bridged:

1. **Async generator vs sync call.** ADK's primary entry point,
   ``Runner.run_async``, is an *async generator* yielding ``Event`` objects,
   while Penelope's :class:`Target` contract is synchronous. The real interaction
   lives in :meth:`GoogleADKTarget.a_send_message`; the sync
   :meth:`GoogleADKTarget.send_message` drives it, handling the case where an
   event loop is already running.
2. **``conversation_id`` vs ADK session.** ADK holds multi-turn state in a
   ``SessionService`` keyed by a session id. Penelope's string
   ``conversation_id`` is used *directly* as that session id, so Penelope
   transcripts and Rhesis traces line up on the same key.
3. **Framework objects vs JSON.** Penelope's executor serializes the response
   metadata with ``json.dumps`` and no fallback encoder, so every ADK/pydantic
   object put in there has to be reduced to primitives first.

``google.adk`` is intentionally **not** imported at module load time: the runner
is duck-typed, and the two imports that are unavoidable (``Runner`` when wrapping
a bare agent, and ``google.genai.types`` to build the user message) are deferred
into method bodies. Importing this module therefore never hard-requires ADK.

Usage::

    >>> from google.adk.agents import Agent
    >>> from google.adk.runners import Runner
    >>> from google.adk.sessions import InMemorySessionService
    >>>
    >>> agent = Agent(name="support", model="gemini-3-flash", instruction="Help.")
    >>> runner = Runner(agent=agent, app_name="support", session_service=InMemorySessionService())
    >>> target = GoogleADKTarget(runner, "adk-bot", "My ADK agent")
    >>> response = target.send_message("Hello!")
    >>> follow_up = target.send_message("And again?", response.conversation_id)

A bare agent works too, and gets an in-memory session service::

    >>> target = GoogleADKTarget(agent, "adk-bot")
"""

import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Dict, List, Optional
from uuid import uuid4

from rhesis.sdk.targets import Target, TargetResponse

logger = logging.getLogger(__name__)

# Default identifiers used when the caller hands over a bare agent instead of a
# fully configured ``Runner``. ``app_name`` scopes sessions inside the session
# service; ``user_id`` is required by every ADK run call.
DEFAULT_APP_NAME = "penelope"
DEFAULT_USER_ID = "penelope-user"


def _json_safe(value: Any) -> Any:
    """
    Coerce an ADK/pydantic object into something ``json.dumps`` can serialize.

    Response metadata is placed into the :class:`TargetResponse` metadata dict,
    which Penelope's executor serializes with ``json.dumps`` *without* a fallback
    encoder. ADK exposes token usage as a ``google.genai`` pydantic model rather
    than a plain dict, so it must be reduced to JSON primitives here to avoid a
    ``TypeError`` the target itself cannot catch.
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


class GoogleADKTarget(Target):
    """
    Target for Google ADK agents.

    Accepts either a configured ``Runner`` (the real ADK entry point, carrying
    the app name, session service and any plugins) or a bare agent, which is
    wrapped in a ``Runner`` with an in-memory session service on first use.
    Multi-turn context is preserved by reusing the ADK session whose id is the
    ``conversation_id`` Penelope threads through each turn.
    """

    def __init__(
        self,
        runner: Any,
        target_id: str,
        description: Optional[str] = None,
        *,
        app_name: Optional[str] = None,
        user_id: str = DEFAULT_USER_ID,
        session_service: Any = None,
    ):
        """
        Initialize the Google ADK target.

        Args:
            runner: An ADK ``Runner``, or a bare ADK agent to wrap in one.
            target_id: Unique identifier for this target.
            description: Human-readable description of what this target does.
            app_name: App name for session scoping. Defaults to the runner's own
                ``app_name`` when one was supplied, else ``"penelope"``.
            user_id: User id passed to every ADK run call.
            session_service: Session service to use when wrapping a bare agent.
                Ignored when ``runner`` is already a ``Runner``.
        """
        self._runner = runner if _looks_like_runner(runner) else None
        self._agent = None if self._runner is not None else runner
        self._explicit_app_name = app_name
        self._session_service = session_service
        self.user_id = user_id
        self._target_id = target_id
        self._description = description or (f"Google ADK {type(runner).__name__}: {target_id}")

        # Sessions we have already prepared, so repeat turns skip the session
        # lookup. Maps the Penelope conversation_id to the ADK session id (the
        # same string; the registry records readiness, not a translation).
        self._sessions: Dict[str, str] = {}

        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid Google ADK target: {error}")

    @property
    def target_type(self) -> str:
        return "google_adk"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    @property
    def app_name(self) -> str:
        """App name used to scope ADK sessions."""
        if self._explicit_app_name:
            return self._explicit_app_name
        if self._runner is not None:
            runner_app = getattr(self._runner, "app_name", None)
            if isinstance(runner_app, str) and runner_app:
                return runner_app
        return DEFAULT_APP_NAME

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate the Google ADK target configuration."""
        if self._runner is None and self._agent is None:
            return False, "Runner or agent cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if self._runner is not None:
            if not callable(getattr(self._runner, "run_async", None)):
                return False, "Runner must have a callable run_async() method"
            return True, None
        # A bare agent is wrapped in a Runner on first use, so all we can check
        # up front is that it looks like an ADK agent at all.
        if not isinstance(getattr(self._agent, "name", None), str):
            return False, "Agent must have a name (is this a Google ADK agent?)"
        return True, None

    def is_stateful(self) -> bool:
        """Whether a session service is available to hold conversation history.

        ADK's session service *is* the conversation memory, so this is true for
        every ordinary configuration; it is false only if a caller hands over a
        runner built without one.
        """
        return self._resolve_session_service() is not None or self._runner is None

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Send a message to the ADK agent (synchronous entry point).

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
        Send a message to the ADK agent (native async entry point).

        Penelope's executor awaits this directly, so the real interaction is
        implemented here. Any exception is converted into an unsuccessful
        :class:`TargetResponse`; this method never raises.

        Note:
            ``files`` is accepted for interface compatibility but ignored. ADK
            does support multimodal parts, but Penelope's file contract does not
            map onto them cleanly enough to guess at; attach content through the
            agent instead.
        """
        if not message or not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            session_id = conversation_id or uuid4().hex
            runner = self._resolve_runner()
            await self._ensure_session(runner, session_id)
            events = await self._collect_events(runner, message, session_id, **kwargs)
            content = self._extract_reply(events)

            if content is None:
                return TargetResponse(
                    success=False,
                    content="",
                    conversation_id=session_id,
                    error="Google ADK run produced no text response",
                    metadata=self._build_metadata(message, session_id, events),
                )

            return TargetResponse(
                success=True,
                content=content,
                conversation_id=session_id,
                metadata=self._build_metadata(message, session_id, events),
            )
        except Exception as e:
            # The contract is that this never raises, so the traceback would
            # otherwise be lost entirely; the type goes in the message because
            # some ADK errors stringify to something uninformative on their own.
            logger.debug("Google ADK target turn failed", exc_info=True)
            return TargetResponse(
                success=False,
                content="",
                error=f"Google ADK error: {type(e).__name__}: {e}",
            )

    def _resolve_runner(self) -> Any:
        """Return the ``Runner``, building one around a bare agent on first use.

        The ``google.adk`` imports live here rather than at module scope so that
        importing this module never requires ADK to be installed.
        """
        if self._runner is not None:
            return self._runner

        from google.adk.runners import Runner

        if self._session_service is None:
            from google.adk.sessions import InMemorySessionService

            self._session_service = InMemorySessionService()

        self._runner = Runner(
            agent=self._agent,
            app_name=self.app_name,
            session_service=self._session_service,
        )
        return self._runner

    def _resolve_session_service(self) -> Any:
        """Return the runner's session service, if it has one."""
        if self._runner is not None:
            return getattr(self._runner, "session_service", None)
        return self._session_service

    async def _ensure_session(self, runner: Any, session_id: str) -> None:
        """
        Make sure an ADK session exists for ``session_id``.

        Looked up before being created, which is what makes a caller-supplied id
        work and what lets a persistent session service (``DatabaseSessionService``,
        ``VertexAiSessionService``) resume a conversation that started in another
        process. The result is cached so later turns skip the round-trip.
        """
        if session_id in self._sessions:
            return

        service = getattr(runner, "session_service", None)
        if service is None:
            # A runner without a session service cannot hold history; the run
            # call below will surface whatever ADK does about that.
            self._sessions[session_id] = session_id
            return

        existing = None
        get_session = getattr(service, "get_session", None)
        if callable(get_session):
            try:
                existing = await _maybe_await(
                    get_session(
                        app_name=self.app_name,
                        user_id=self.user_id,
                        session_id=session_id,
                    )
                )
            except Exception:
                # Session services differ in how they report "not found"; treat
                # any lookup failure as absent and try to create instead.
                existing = None

        if existing is None:
            await _maybe_await(
                service.create_session(
                    app_name=self.app_name,
                    user_id=self.user_id,
                    session_id=session_id,
                )
            )
        self._sessions[session_id] = session_id

    async def _collect_events(
        self, runner: Any, message: str, session_id: str, **kwargs: Any
    ) -> List[Any]:
        """Drive one ADK turn and collect every event it yields."""
        from google.genai import types

        new_message = types.Content(role="user", parts=[types.Part(text=message)])
        events: List[Any] = []
        async for event in runner.run_async(
            user_id=self.user_id,
            session_id=session_id,
            new_message=new_message,
            **kwargs,
        ):
            events.append(event)
        return events

    @staticmethod
    def _event_text(event: Any) -> str:
        """Concatenate the text parts of an event's content."""
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) or ()
        return "".join(part.text for part in parts if isinstance(getattr(part, "text", None), str))

    def _extract_reply(self, events: List[Any]) -> Optional[str]:
        """
        Pull the assistant's reply out of ADK's event stream.

        Preference order:

        1. the last event ADK itself marks as a final response and that carries
           text -- the normal case, and the only one that is unambiguous when
           several agents each produce a final response in one invocation;
        2. the last complete (non-partial) event with text, for agents that never
           set the final-response flag;
        3. any text seen at all, which is what streaming leaves behind when every
           event is partial.

        Returns ``None`` when there is no text anywhere -- e.g. a turn that ended
        on a tool result. The caller reports that as an unsuccessful response
        rather than as a successful empty one.
        """
        final_texts = []
        complete_texts = []
        any_texts = []
        for event in events:
            text = self._event_text(event)
            if not text:
                continue
            any_texts.append(text)
            if not getattr(event, "partial", False):
                complete_texts.append(text)
            is_final = getattr(event, "is_final_response", None)
            try:
                if callable(is_final) and is_final():
                    final_texts.append(text)
            except Exception:
                pass

        for candidate in (final_texts, complete_texts, any_texts):
            if candidate:
                return candidate[-1]
        return None

    def _build_metadata(self, message: str, session_id: str, events: List[Any]) -> Dict[str, Any]:
        """Collect useful, JSON-safe detail without crashing on missing fields."""
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        tools_called: List[str] = []
        agents: List[str] = []
        invocation_id = None

        for event in events:
            usage = getattr(event, "usage_metadata", None)
            if usage is not None:
                input_tokens += getattr(usage, "prompt_token_count", None) or 0
                output_tokens += getattr(usage, "candidates_token_count", None) or 0
                total_tokens += getattr(usage, "total_token_count", None) or 0
            get_calls = getattr(event, "get_function_calls", None)
            if callable(get_calls):
                try:
                    tools_called.extend(
                        call.name for call in get_calls() or () if getattr(call, "name", None)
                    )
                except Exception:
                    pass
            author = getattr(event, "author", None)
            if isinstance(author, str) and author and author not in agents:
                agents.append(author)
            if invocation_id is None:
                candidate = getattr(event, "invocation_id", None)
                if isinstance(candidate, str) and candidate:
                    invocation_id = candidate

        metadata: Dict[str, Any] = {
            "input_sent": message,
            "session_id": session_id,
            "app_name": self.app_name,
            "runner_type": type(self._runner).__name__ if self._runner else None,
            "event_count": len(events),
            "agents_involved": agents,
            "tools_called": tools_called,
        }
        if invocation_id is not None:
            metadata["invocation_id"] = invocation_id
        if total_tokens or input_tokens or output_tokens:
            metadata["input_tokens"] = input_tokens
            metadata["output_tokens"] = output_tokens
            metadata["total_tokens"] = total_tokens
        return _json_safe(metadata)

    @staticmethod
    def _run_coroutine(coro: Awaitable[Any]) -> Any:
        """
        Run an awaitable to completion from synchronous code.

        Uses :func:`asyncio.run` when no event loop is active. If a loop is
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
            memory = "Yes (ADK session service holds the conversation history)"
            continuity = (
                "Maintain conversation_id for conversation continuity across multiple turns.\n"
                "It is used directly as the ADK session id, so the agent sees the full\n"
                "conversation context; the first turn returns a new conversation_id to reuse."
            )
        else:
            memory = "No (runner has no session service; each turn is independent)"
            continuity = (
                "This runner was built without a session service, so each message is\n"
                "independent. A conversation_id is still returned for tracking, but it\n"
                "does not restore prior context."
            )
        subject = self._runner if self._runner is not None else self._agent
        return f"""
Target: {self._description}
Type: Google ADK {type(subject).__name__}
Memory: {memory}

Send messages using send_message_to_target(message, conversation_id).
{continuity}
"""

    def clear_session(self, conversation_id: str) -> None:
        """
        Forget our record of an ADK session so the next turn re-resolves it.

        Args:
            conversation_id: The conversation to clear.

        Note:
            This drops the adapter's cache only; the session itself stays in the
            ADK session service, so a later turn with the same id still resumes
            the prior history. Delete it through the session service to erase it.
        """
        self._sessions.pop(conversation_id, None)


def _looks_like_runner(candidate: Any) -> bool:
    """Whether ``candidate`` is an ADK ``Runner`` rather than a bare agent.

    Duck-typed instead of ``isinstance``: importing ``google.adk.runners`` at
    module scope would make ADK a hard dependency of this module. A runner is the
    thing that can drive a turn (``run_async``) and owns the session service; an
    agent has neither.
    """
    return callable(getattr(candidate, "run_async", None)) and hasattr(candidate, "session_service")


async def _maybe_await(value: Any) -> Any:
    """Await ``value`` if it is awaitable, else return it as-is.

    ADK's session-service methods are coroutines, but callers occasionally supply
    a simplified synchronous stand-in.
    """
    if inspect.isawaitable(value):
        return await value
    return value

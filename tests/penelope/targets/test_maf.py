"""Tests for MAFTarget.

These tests use lightweight fakes that mimic the MAF (Microsoft Agent Framework)
agent contract, so no LLM or network access is required.  Two fakes are
provided to cover both the modern (``create_session`` / ``run(session=...)``)
and legacy (``get_new_thread`` / ``run(thread=...)``) MAF API shapes.
"""

import inspect
import json
from typing import Any

import pytest

from rhesis.penelope.targets.maf import MAFTarget
from rhesis.sdk.targets import Target, TargetResponse


class FakeResponse:
    """Stand-in for a MAF ``AgentRunResponse`` / ``AgentResponse``."""

    def __init__(self, text: str):
        self.text = text
        self.response_id = "resp-abc"
        self.usage = {"total_tokens": 7}


class FakeSession:
    """Stand-in for a MAF ``AgentThread`` / ``AgentSession`` object."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: list[str] = []


class ModernFakeAgent:
    """MAF agent exposing the modern ``create_session`` + ``run(session=...)`` API."""

    def __init__(self, raises: bool = False):
        self._counter = 0
        self._raises = raises
        self.calls: list[tuple[str, FakeSession | None]] = []

    def create_session(self, *, session_id: str | None = None) -> FakeSession:
        self._counter += 1
        return FakeSession(session_id or f"session-{self._counter}")

    async def run(self, messages: str | None = None, *, session: FakeSession | None = None):
        self.calls.append((messages, session))
        if self._raises:
            raise RuntimeError("boom inside agent")
        if session is not None:
            session.history.append(messages or "")
        turn = len(session.history) if session is not None else 1
        return FakeResponse(f"reply to '{messages}' (turn {turn})")


class ModernFakeAgentWithKwargs:
    """MAF agent with ``**kwargs`` in ``run`` (common in real MAF builds)."""

    def __init__(self):
        self._counter = 0
        self.calls: list[tuple[str, FakeSession | None, dict[str, Any]]] = []

    def create_session(self, *, session_id: str | None = None) -> FakeSession:
        self._counter += 1
        return FakeSession(session_id or f"session-{self._counter}")

    async def run(self, messages: str | None = None, **kwargs):
        session = kwargs.get("session")
        self.calls.append((messages, session, kwargs))
        if session is not None:
            session.history.append(messages or "")
        turn = len(session.history) if session is not None else 1
        return FakeResponse(f"kwargs reply to '{messages}' (turn {turn})")


class MixedShapeFakeAgent:
    """Mixed-shape agent: ``create_session`` but ``run(..., thread=..., **kwargs)``.

    ``run`` honors the explicit ``thread`` parameter and would silently drop a
    ``session`` passed via ``**kwargs``.  The target must therefore prefer the
    explicitly declared ``thread`` over routing ``session`` through ``**kwargs``.
    """

    def __init__(self):
        self._counter = 0
        self.calls: list[tuple[str, FakeSession | None, dict[str, Any]]] = []

    def create_session(self, *, session_id: str | None = None) -> FakeSession:
        self._counter += 1
        return FakeSession(session_id or f"session-{self._counter}")

    async def run(
        self, messages: str | None = None, *, thread: FakeSession | None = None, **kwargs
    ):
        self.calls.append((messages, thread, kwargs))
        if thread is not None:
            thread.history.append(messages or "")
        turn = len(thread.history) if thread is not None else 1
        return FakeResponse(f"mixed reply to '{messages}' (turn {turn})")


class LegacyFakeAgent:
    """MAF agent exposing the legacy ``get_new_thread`` + ``run(thread=...)`` API."""

    def __init__(self):
        self._counter = 0
        self.calls: list[tuple[str, FakeSession | None]] = []

    def get_new_thread(self) -> FakeSession:
        self._counter += 1
        return FakeSession(f"thread-{self._counter}")

    async def run(self, messages: str | None = None, *, thread: FakeSession | None = None):
        self.calls.append((messages, thread))
        if thread is not None:
            thread.history.append(messages or "")
        return FakeResponse(f"legacy reply to '{messages}'")


@pytest.fixture
def modern_agent() -> ModernFakeAgent:
    return ModernFakeAgent()


@pytest.fixture
def target(modern_agent: ModernFakeAgent) -> MAFTarget:
    return MAFTarget(modern_agent, "maf-bot", "A MAF test agent")


def test_is_a_target(target: MAFTarget):
    assert isinstance(target, Target)


def test_identity_properties(target: MAFTarget):
    assert target.target_type == "maf"
    assert isinstance(target.target_id, str) and target.target_id
    assert isinstance(target.description, str) and target.description


def test_validate_configuration_good(target: MAFTarget):
    assert target.validate_configuration() == (True, None)


def test_validate_configuration_none_agent(target: MAFTarget):
    target.agent = None
    is_valid, error = target.validate_configuration()
    assert is_valid is False
    assert isinstance(error, str) and error


def test_init_rejects_none_agent():
    with pytest.raises(ValueError, match="Invalid MAF target"):
        MAFTarget(None, "maf-bot")


def test_init_rejects_agent_without_run():
    class NoRun:
        pass

    with pytest.raises(ValueError, match="callable async run"):
        MAFTarget(NoRun(), "maf-bot")


def test_send_message_success(target: MAFTarget):
    response = target.send_message("hello")
    assert isinstance(response, TargetResponse)
    assert response.success is True
    assert response.content
    assert response.error is None
    assert response.conversation_id
    assert response.metadata["input_sent"] == "hello"
    assert response.metadata["agent_type"] == "ModernFakeAgent"
    assert response.metadata["response_id"] == "resp-abc"


@pytest.mark.parametrize("message", ["", "   ", "\n\t"])
def test_send_message_empty_does_not_raise(target: MAFTarget, message: str):
    response = target.send_message(message)
    assert response.success is False
    assert response.error == "Empty message"


def test_agent_exception_surfaces_as_failure():
    agent = ModernFakeAgent(raises=True)
    target = MAFTarget(agent, "maf-bot")
    response = target.send_message("hello")
    assert response.success is False
    assert response.content == ""
    assert response.error and "MAF error" in response.error


def test_multi_turn_preserves_thread(target: MAFTarget, modern_agent):
    first = target.send_message("turn one")
    conv_id = first.conversation_id
    assert conv_id

    second = target.send_message("turn two", conversation_id=conv_id)
    assert second.conversation_id == conv_id

    # The same session object must be reused across both turns.
    session_turn1 = modern_agent.calls[0][1]
    session_turn2 = modern_agent.calls[1][1]
    assert session_turn1 is session_turn2
    assert session_turn1 is not None
    assert session_turn1.history == ["turn one", "turn two"]


def test_unknown_conversation_id_gets_fresh_thread(target: MAFTarget):
    response = target.send_message("hi", conversation_id="caller-supplied-id")
    assert response.success is True
    assert response.conversation_id == "caller-supplied-id"


def test_a_send_message_is_coroutine_function(target: MAFTarget):
    assert inspect.iscoroutinefunction(target.a_send_message)


async def test_a_send_message_returns_valid_response(target: MAFTarget):
    response = await target.a_send_message("hello async")
    assert isinstance(response, TargetResponse)
    assert response.success is True
    assert response.content
    assert response.conversation_id


async def test_send_message_works_inside_running_loop(target: MAFTarget):
    # Called from within an active event loop -> exercises the worker-thread bridge.
    response = target.send_message("from inside loop")
    assert response.success is True
    assert response.content


def test_legacy_thread_api_multi_turn():
    agent = LegacyFakeAgent()
    target = MAFTarget(agent, "legacy-bot")

    first = target.send_message("turn one")
    second = target.send_message("turn two", conversation_id=first.conversation_id)

    assert second.conversation_id == first.conversation_id
    assert agent.calls[0][1] is agent.calls[1][1]
    assert agent.calls[0][1].history == ["turn one", "turn two"]


def test_kwargs_run_uses_session_for_modern_agent():
    agent = ModernFakeAgentWithKwargs()
    target = MAFTarget(agent, "kwargs-bot")

    first = target.send_message("turn one")
    second = target.send_message("turn two", conversation_id=first.conversation_id)

    assert second.conversation_id == first.conversation_id
    assert agent.calls[0][1] is agent.calls[1][1]
    assert "session" in agent.calls[0][2]
    assert "thread" not in agent.calls[0][2]
    assert agent.calls[0][1].history == ["turn one", "turn two"]


def test_mixed_shape_prefers_explicit_thread_over_kwargs():
    # create_session() suggests session=, but run() explicitly declares thread=
    # and only honors that; an explicit param must win over the **kwargs channel
    # so conversation memory is not silently dropped.
    agent = MixedShapeFakeAgent()
    target = MAFTarget(agent, "mixed-bot")

    first = target.send_message("turn one")
    second = target.send_message("turn two", conversation_id=first.conversation_id)

    assert second.conversation_id == first.conversation_id
    # State was passed under the explicit ``thread`` param, not through **kwargs.
    assert agent.calls[0][1] is not None
    assert "session" not in agent.calls[0][2]
    assert agent.calls[0][1] is agent.calls[1][1]
    assert agent.calls[0][1].history == ["turn one", "turn two"]


class NonSerializableUsage:
    """Object-style ``usage`` like real MAF returns (not a plain dict)."""

    def __init__(self):
        self.total_tokens = 42

    def model_dump(self, *args: Any, **kwargs: Any) -> dict:
        return {"total_tokens": self.total_tokens}


class OpaqueUsage:
    """Framework object with no ``model_dump`` (must fall back to ``str``)."""

    def __repr__(self) -> str:
        return "OpaqueUsage(total_tokens=99)"


class ResponseWithObjectUsage:
    def __init__(self, usage: Any):
        self.text = "hello"
        self.usage = usage


class StatelessAgent:
    """MAF agent with no thread/session factory (each turn is independent)."""

    async def run(self, messages: str | None = None):
        return FakeResponse(f"stateless reply to '{messages}'")


def test_metadata_is_json_serializable_with_object_usage():
    # Real MAF returns framework objects for ``usage``; metadata must stay
    # JSON-serializable because the executor json.dumps() it without a fallback.
    class AgentWithObjectUsage(ModernFakeAgent):
        async def run(self, messages: str | None = None, *, session=None):
            return ResponseWithObjectUsage(NonSerializableUsage())

    target = MAFTarget(AgentWithObjectUsage(), "usage-bot")
    response = target.send_message("hi")

    assert response.success is True
    # Must not raise -> this is the crash the fix prevents.
    json.dumps(response.metadata)
    assert response.metadata["usage"] == {"total_tokens": 42}


def test_metadata_coerces_opaque_usage_to_string():
    class AgentWithOpaqueUsage(ModernFakeAgent):
        async def run(self, messages: str | None = None, *, session=None):
            return ResponseWithObjectUsage(OpaqueUsage())

    target = MAFTarget(AgentWithOpaqueUsage(), "usage-bot")
    response = target.send_message("hi")

    assert response.success is True
    json.dumps(response.metadata)
    assert response.metadata["usage"] == "OpaqueUsage(total_tokens=99)"


def test_stateless_agent_reports_no_memory():
    target = MAFTarget(StatelessAgent(), "stateless-bot")
    assert target.is_stateful() is False
    doc = target.get_tool_documentation()
    assert "Memory: No" in doc
    # Still returns a conversation_id for tracking, just without restored context.
    response = target.send_message("hi")
    assert response.success is True
    assert response.conversation_id


def test_deprecated_module_alias_still_works():
    import sys
    import warnings

    sys.modules.pop("rhesis.penelope.targets.microsoft_agent_framework", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from rhesis.penelope.targets.microsoft_agent_framework import (
            MicrosoftAgentFrameworkTarget,
        )

    assert MicrosoftAgentFrameworkTarget is MAFTarget
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_deprecated_package_aliases_warn():
    import warnings

    import rhesis.penelope as pen
    import rhesis.penelope.targets as targets_pkg

    for module in (pen, targets_pkg):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            alias = module.MicrosoftAgentFrameworkTarget
        assert alias is MAFTarget
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_get_tool_documentation(target: MAFTarget):
    doc = target.get_tool_documentation()
    assert "MAF" in doc
    assert "conversation_id" in doc
    assert "send_message_to_target" in doc


def test_clear_session(target: MAFTarget):
    first = target.send_message("hello")
    conv_id = first.conversation_id
    assert conv_id in target._threads
    target.clear_session(conv_id)
    assert conv_id not in target._threads

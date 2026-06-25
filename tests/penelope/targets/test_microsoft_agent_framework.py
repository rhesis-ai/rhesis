"""Tests for MicrosoftAgentFrameworkTarget.

These tests use lightweight fakes that mimic the Microsoft Agent Framework
(MAF) agent contract, so no LLM or network access is required.  Two fakes are
provided to cover both the modern (``create_session`` / ``run(session=...)``)
and legacy (``get_new_thread`` / ``run(thread=...)``) MAF API shapes.
"""

import inspect

import pytest

from rhesis.penelope.targets.microsoft_agent_framework import MicrosoftAgentFrameworkTarget
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
def target(modern_agent: ModernFakeAgent) -> MicrosoftAgentFrameworkTarget:
    return MicrosoftAgentFrameworkTarget(modern_agent, "maf-bot", "A MAF test agent")


def test_is_a_target(target: MicrosoftAgentFrameworkTarget):
    assert isinstance(target, Target)


def test_identity_properties(target: MicrosoftAgentFrameworkTarget):
    assert target.target_type == "microsoft_agent_framework"
    assert isinstance(target.target_id, str) and target.target_id
    assert isinstance(target.description, str) and target.description


def test_validate_configuration_good(target: MicrosoftAgentFrameworkTarget):
    assert target.validate_configuration() == (True, None)


def test_validate_configuration_none_agent(target: MicrosoftAgentFrameworkTarget):
    target.agent = None
    is_valid, error = target.validate_configuration()
    assert is_valid is False
    assert isinstance(error, str) and error


def test_init_rejects_none_agent():
    with pytest.raises(ValueError, match="Invalid Microsoft Agent Framework target"):
        MicrosoftAgentFrameworkTarget(None, "maf-bot")


def test_init_rejects_agent_without_run():
    class NoRun:
        pass

    with pytest.raises(ValueError, match="callable async run"):
        MicrosoftAgentFrameworkTarget(NoRun(), "maf-bot")


def test_send_message_success(target: MicrosoftAgentFrameworkTarget):
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
def test_send_message_empty_does_not_raise(target: MicrosoftAgentFrameworkTarget, message: str):
    response = target.send_message(message)
    assert response.success is False
    assert response.error == "Empty message"


def test_agent_exception_surfaces_as_failure():
    agent = ModernFakeAgent(raises=True)
    target = MicrosoftAgentFrameworkTarget(agent, "maf-bot")
    response = target.send_message("hello")
    assert response.success is False
    assert response.content == ""
    assert response.error and "Microsoft Agent Framework error" in response.error


def test_multi_turn_preserves_thread(target: MicrosoftAgentFrameworkTarget, modern_agent):
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


def test_unknown_conversation_id_gets_fresh_thread(target: MicrosoftAgentFrameworkTarget):
    response = target.send_message("hi", conversation_id="caller-supplied-id")
    assert response.success is True
    assert response.conversation_id == "caller-supplied-id"


def test_a_send_message_is_coroutine_function(target: MicrosoftAgentFrameworkTarget):
    assert inspect.iscoroutinefunction(target.a_send_message)


async def test_a_send_message_returns_valid_response(target: MicrosoftAgentFrameworkTarget):
    response = await target.a_send_message("hello async")
    assert isinstance(response, TargetResponse)
    assert response.success is True
    assert response.content
    assert response.conversation_id


async def test_send_message_works_inside_running_loop(target: MicrosoftAgentFrameworkTarget):
    # Called from within an active event loop -> exercises the worker-thread bridge.
    response = target.send_message("from inside loop")
    assert response.success is True
    assert response.content


def test_legacy_thread_api_multi_turn():
    agent = LegacyFakeAgent()
    target = MicrosoftAgentFrameworkTarget(agent, "legacy-bot")

    first = target.send_message("turn one")
    second = target.send_message("turn two", conversation_id=first.conversation_id)

    assert second.conversation_id == first.conversation_id
    assert agent.calls[0][1] is agent.calls[1][1]
    assert agent.calls[0][1].history == ["turn one", "turn two"]


def test_get_tool_documentation(target: MicrosoftAgentFrameworkTarget):
    doc = target.get_tool_documentation()
    assert "Microsoft Agent Framework" in doc
    assert "conversation_id" in doc
    assert "send_message_to_target" in doc


def test_clear_session(target: MicrosoftAgentFrameworkTarget):
    first = target.send_message("hello")
    conv_id = first.conversation_id
    assert conv_id in target._threads
    target.clear_session(conv_id)
    assert conv_id not in target._threads

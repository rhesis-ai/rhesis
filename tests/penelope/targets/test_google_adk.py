"""Tests for the Google ADK Penelope target.

Everything here runs against fakes: no LLM, no network, and deliberately no
``google.adk`` import, because the target duck-types the runner and must stay
importable without ADK installed (see ``test_optional_imports.py``).

The fakes mirror the parts of ADK's contract the target actually touches: a
``Runner`` exposing ``run_async`` as an async generator plus a ``session_service``
with async ``get_session`` / ``create_session``, and ``Event``-shaped objects with
``content.parts[].text``, ``partial``, ``is_final_response()``,
``get_function_calls()``, ``usage_metadata``, ``author`` and ``invocation_id``.
"""

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from rhesis.penelope.targets import GoogleADKTarget
from rhesis.sdk.targets import Target

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakePart:
    text: Optional[str] = None


@dataclass
class FakeContent:
    role: str = "model"
    parts: list = field(default_factory=list)


@dataclass
class FakeFunctionCall:
    name: str


class FakeEvent:
    """An ADK-``Event``-shaped object covering the fields the target reads."""

    def __init__(
        self,
        text: Optional[str] = None,
        *,
        partial: bool = False,
        final: bool = True,
        function_calls: Optional[list] = None,
        usage: Any = None,
        author: str = "root_agent",
        invocation_id: str = "e-inv-1",
    ):
        self.content = FakeContent(parts=[FakePart(text=text)]) if text is not None else None
        self.partial = partial
        self._final = final
        self._function_calls = function_calls or []
        self.usage_metadata = usage
        self.author = author
        self.invocation_id = invocation_id

    def is_final_response(self) -> bool:
        return self._final

    def get_function_calls(self) -> list:
        return self._function_calls


class FakeUsage:
    """Stands in for ``google.genai`` usage metadata: a pydantic model, not a dict."""

    def __init__(self, prompt: int, candidates: int, total: int) -> None:
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.total_token_count = total

    def model_dump(self, mode: str = "python") -> dict:
        return {
            "prompt_token_count": self.prompt_token_count,
            "candidates_token_count": self.candidates_token_count,
            "total_token_count": self.total_token_count,
        }


class NonSerializableUsage:
    """Usage metadata with no ``model_dump`` and no JSON-friendly repr."""

    def __init__(self) -> None:
        self.prompt_token_count = 3
        self.candidates_token_count = 4
        self.total_token_count = 7

    def __repr__(self) -> str:
        return "NonSerializableUsage(total=7)"


class FakeSessionService:
    """Minimal async session service with an inspectable call log."""

    def __init__(self, *, existing: Optional[set] = None) -> None:
        self.sessions: set = set(existing or ())
        self.created: list = []
        self.looked_up: list = []

    async def get_session(self, *, app_name: str, user_id: str, session_id: str):
        self.looked_up.append(session_id)
        return {"id": session_id} if session_id in self.sessions else None

    async def create_session(self, *, app_name: str, user_id: str, session_id: str):
        self.created.append(session_id)
        self.sessions.add(session_id)
        return {"id": session_id}


class FakeRunner:
    """A ``Runner``-shaped object whose ``run_async`` is an async generator."""

    def __init__(self, scripts=None, *, session_service=None, app_name="fake-app") -> None:
        # Maps session id -> list of event lists, one per turn.
        self.scripts = scripts if scripts is not None else {}
        self.session_service = session_service or FakeSessionService()
        self.app_name = app_name
        self.calls: list = []
        self._turn_index: dict = {}

    async def run_async(self, *, user_id, session_id, new_message, **kwargs):
        text = "".join(part.text for part in new_message.parts if getattr(part, "text", None))
        self.calls.append({"session_id": session_id, "user_id": user_id, "message": text})
        turns = self.scripts.get(session_id) or self.scripts.get("*") or [[FakeEvent("ok")]]
        index = self._turn_index.get(session_id, 0)
        self._turn_index[session_id] = index + 1
        for event in turns[min(index, len(turns) - 1)]:
            yield event


class ExplodingRunner(FakeRunner):
    async def run_async(self, *, user_id, session_id, new_message, **kwargs):
        raise RuntimeError("model unavailable")
        yield  # pragma: no cover - unreachable, keeps this an async generator


class FakeAgent:
    """A bare ADK-agent-shaped object: has a name, cannot drive a turn."""

    def __init__(self, name: str = "bare_agent") -> None:
        self.name = name
        self.description = "A bare agent"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner({"*": [[FakeEvent("Hello from ADK.")]]})


@pytest.fixture
def target(runner: FakeRunner) -> GoogleADKTarget:
    return GoogleADKTarget(runner, "adk-bot", "My ADK agent")


# ---------------------------------------------------------------------------
# Identity and validation
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_is_a_target(self, target):
        assert isinstance(target, Target)

    def test_target_type(self, target):
        assert target.target_type == "google_adk"

    def test_target_id_and_description(self, target):
        assert target.target_id == "adk-bot"
        assert target.description == "My ADK agent"

    def test_default_description(self, runner):
        assert GoogleADKTarget(runner, "adk-bot").description == ("Google ADK FakeRunner: adk-bot")

    def test_app_name_comes_from_the_runner(self, target):
        assert target.app_name == "fake-app"

    def test_explicit_app_name_wins(self, runner):
        target = GoogleADKTarget(runner, "adk-bot", app_name="override")
        assert target.app_name == "override"

    def test_a_send_message_is_natively_async(self, target):
        assert inspect.iscoroutinefunction(target.a_send_message)


class TestValidation:
    def test_valid_runner(self, target):
        assert target.validate_configuration() == (True, None)

    def test_none_is_rejected(self):
        with pytest.raises(ValueError, match="Runner or agent cannot be None"):
            GoogleADKTarget(None, "adk-bot")

    def test_empty_target_id_is_rejected(self, runner):
        with pytest.raises(ValueError, match="target_id cannot be empty"):
            GoogleADKTarget(runner, "")

    def test_runner_without_run_async_is_rejected(self):
        class Broken:
            session_service = FakeSessionService()

        with pytest.raises(ValueError, match="name"):
            GoogleADKTarget(Broken(), "adk-bot")

    def test_object_that_is_neither_runner_nor_agent_is_rejected(self):
        with pytest.raises(ValueError, match="Google ADK agent"):
            GoogleADKTarget(object(), "adk-bot")


# ---------------------------------------------------------------------------
# Sending messages
# ---------------------------------------------------------------------------


class TestSendMessage:
    def test_successful_turn(self, target):
        response = target.send_message("Hi there")
        assert response.success is True
        assert response.content == "Hello from ADK."
        assert response.conversation_id

    def test_first_turn_creates_the_session(self, target, runner):
        response = target.send_message("Hi there")
        assert runner.session_service.created == [response.conversation_id]

    def test_message_reaches_the_runner(self, target, runner):
        target.send_message("Hi there")
        assert runner.calls[0]["message"] == "Hi there"
        assert runner.calls[0]["user_id"] == "penelope-user"

    @pytest.mark.parametrize("message", ["", "   ", "\n\t"])
    def test_empty_messages_short_circuit(self, target, message):
        response = target.send_message(message)
        assert response.success is False
        assert response.error == "Empty message"

    def test_runner_failure_becomes_an_unsuccessful_response(self):
        target = GoogleADKTarget(ExplodingRunner(), "adk-bot")
        response = target.send_message("Hi")
        assert response.success is False
        assert "Google ADK error" in response.error
        assert "model unavailable" in response.error

    @pytest.mark.asyncio
    async def test_async_entry_point(self, target):
        response = await target.a_send_message("Hi there")
        assert response.success is True
        assert response.content == "Hello from ADK."

    @pytest.mark.asyncio
    async def test_sync_entry_point_works_inside_a_running_loop(self, target):
        """``asyncio.run`` would raise here, so it must fall back to a worker thread."""
        response = await asyncio.to_thread(target.send_message, "Hi there")
        assert response.success is True


class TestMultiTurnContinuity:
    def test_conversation_id_is_reused_as_the_session_id(self, runner):
        target = GoogleADKTarget(runner, "adk-bot")
        first = target.send_message("turn one")
        second = target.send_message("turn two", first.conversation_id)

        assert second.conversation_id == first.conversation_id
        assert [call["session_id"] for call in runner.calls] == [
            first.conversation_id,
            first.conversation_id,
        ]

    def test_the_session_is_created_only_once(self, runner):
        target = GoogleADKTarget(runner, "adk-bot")
        first = target.send_message("turn one")
        target.send_message("turn two", first.conversation_id)
        assert runner.session_service.created == [first.conversation_id]

    def test_unknown_caller_supplied_id_is_created(self, runner):
        target = GoogleADKTarget(runner, "adk-bot")
        response = target.send_message("hello", "id-the-target-never-saw")
        assert response.success is True
        assert response.conversation_id == "id-the-target-never-saw"
        assert runner.session_service.created == ["id-the-target-never-saw"]

    def test_a_pre_existing_session_is_resumed_not_recreated(self):
        """A persistent session service should keep history from another process."""
        service = FakeSessionService(existing={"already-there"})
        runner = FakeRunner({"*": [[FakeEvent("resumed")]]}, session_service=service)
        target = GoogleADKTarget(runner, "adk-bot")

        response = target.send_message("hello", "already-there")
        assert response.success is True
        assert service.looked_up == ["already-there"]
        assert service.created == []

    def test_clear_session_forgets_our_cache_only(self, runner):
        target = GoogleADKTarget(runner, "adk-bot")
        first = target.send_message("turn one")
        assert first.conversation_id in target._sessions

        target.clear_session(first.conversation_id)
        assert first.conversation_id not in target._sessions

        # The session still exists in the service, so the next turn resumes it.
        target.send_message("turn two", first.conversation_id)
        assert runner.session_service.created == [first.conversation_id]

    def test_session_lookup_failure_falls_back_to_creating(self):
        class GrumpyService(FakeSessionService):
            async def get_session(self, *, app_name, user_id, session_id):
                raise KeyError("no such session")

        runner = FakeRunner({"*": [[FakeEvent("ok")]]}, session_service=GrumpyService())
        target = GoogleADKTarget(runner, "adk-bot")
        response = target.send_message("hello", "some-id")
        assert response.success is True
        assert runner.session_service.created == ["some-id"]


class TestReplyExtraction:
    def test_final_response_event_wins(self):
        runner = FakeRunner(
            {
                "*": [
                    [
                        FakeEvent("thinking out loud", final=False),
                        FakeEvent("the actual answer", final=True),
                    ]
                ]
            }
        )
        target = GoogleADKTarget(runner, "adk-bot")
        assert target.send_message("hi").content == "the actual answer"

    def test_last_final_response_wins_when_several_agents_answer(self):
        runner = FakeRunner(
            {
                "*": [
                    [
                        FakeEvent("sub-agent answer", author="specialist"),
                        FakeEvent("coordinator answer", author="root_agent"),
                    ]
                ]
            }
        )
        target = GoogleADKTarget(runner, "adk-bot")
        assert target.send_message("hi").content == "coordinator answer"

    def test_falls_back_to_the_last_complete_event(self):
        """Some agents never set ADK's final-response flag."""
        runner = FakeRunner(
            {"*": [[FakeEvent("first", final=False), FakeEvent("second", final=False)]]}
        )
        target = GoogleADKTarget(runner, "adk-bot")
        assert target.send_message("hi").content == "second"

    def test_falls_back_to_partial_streaming_text(self):
        runner = FakeRunner(
            {
                "*": [
                    [
                        FakeEvent("chunk one", partial=True, final=False),
                        FakeEvent("chunk two", partial=True, final=False),
                    ]
                ]
            }
        )
        target = GoogleADKTarget(runner, "adk-bot")
        assert target.send_message("hi").content == "chunk two"

    def test_tool_result_only_turn_is_reported_as_a_failure(self):
        """Better an explicit error than a successful empty string."""
        runner = FakeRunner(
            {"*": [[FakeEvent(None, function_calls=[FakeFunctionCall("get_weather")])]]}
        )
        target = GoogleADKTarget(runner, "adk-bot")
        response = target.send_message("hi")
        assert response.success is False
        assert "no text response" in response.error
        assert response.conversation_id

    def test_events_whose_is_final_response_raises_are_tolerated(self):
        class Rude(FakeEvent):
            def is_final_response(self):
                raise RuntimeError("boom")

        runner = FakeRunner({"*": [[Rude("still readable")]]})
        target = GoogleADKTarget(runner, "adk-bot")
        assert target.send_message("hi").content == "still readable"


class TestMetadata:
    def test_metadata_is_json_serializable(self):
        """Penelope's executor json.dumps this dict with no fallback encoder."""
        runner = FakeRunner({"*": [[FakeEvent("answer", usage=FakeUsage(11, 7, 18))]]})
        target = GoogleADKTarget(runner, "adk-bot")
        response = target.send_message("hi")
        # Must not raise -> this is the crash the sanitizing prevents.
        json.dumps(response.metadata)

    def test_non_serializable_usage_is_reduced_to_primitives(self):
        runner = FakeRunner({"*": [[FakeEvent("answer", usage=NonSerializableUsage())]]})
        target = GoogleADKTarget(runner, "adk-bot")
        response = target.send_message("hi")
        json.dumps(response.metadata)
        assert response.metadata["total_tokens"] == 7

    def test_token_usage_is_summed_across_events(self):
        runner = FakeRunner(
            {
                "*": [
                    [
                        FakeEvent("a", usage=FakeUsage(10, 5, 15), final=False),
                        FakeEvent("b", usage=FakeUsage(20, 6, 26)),
                    ]
                ]
            }
        )
        target = GoogleADKTarget(runner, "adk-bot")
        metadata = target.send_message("hi").metadata
        assert metadata["input_tokens"] == 30
        assert metadata["output_tokens"] == 11
        assert metadata["total_tokens"] == 41

    def test_tools_and_agents_are_recorded(self):
        runner = FakeRunner(
            {
                "*": [
                    [
                        FakeEvent(
                            None,
                            function_calls=[FakeFunctionCall("get_weather")],
                            author="root_agent",
                            final=False,
                        ),
                        FakeEvent("done", author="specialist"),
                    ]
                ]
            }
        )
        target = GoogleADKTarget(runner, "adk-bot")
        metadata = target.send_message("hi").metadata
        assert metadata["tools_called"] == ["get_weather"]
        assert metadata["agents_involved"] == ["root_agent", "specialist"]

    def test_core_metadata_fields(self, target):
        metadata = target.send_message("the question").metadata
        assert metadata["input_sent"] == "the question"
        assert metadata["app_name"] == "fake-app"
        assert metadata["runner_type"] == "FakeRunner"
        assert metadata["event_count"] == 1
        assert metadata["invocation_id"] == "e-inv-1"

    def test_metadata_is_present_on_the_failure_path_too(self):
        runner = FakeRunner({"*": [[FakeEvent(None)]]})
        target = GoogleADKTarget(runner, "adk-bot")
        response = target.send_message("hi")
        assert response.success is False
        json.dumps(response.metadata)
        assert response.metadata["input_sent"] == "hi"


class TestBareAgent:
    """A caller with just an agent gets a Runner built for them."""

    def test_bare_agent_is_accepted(self):
        target = GoogleADKTarget(FakeAgent(), "adk-bot")
        assert target.validate_configuration() == (True, None)
        assert target.app_name == "penelope"

    def test_bare_agent_is_wrapped_lazily(self, monkeypatch):
        """Nothing ADK-related is touched until the first turn."""
        agent = FakeAgent()
        target = GoogleADKTarget(agent, "adk-bot")
        assert target._runner is None

        built = FakeRunner({"*": [[FakeEvent("from the built runner")]]})

        def fake_resolve(self):
            self._runner = built
            return built

        monkeypatch.setattr(GoogleADKTarget, "_resolve_runner", fake_resolve)
        response = target.send_message("hi")
        assert response.content == "from the built runner"

    def test_bare_agent_reports_stateful(self):
        """It will be given an in-memory session service, so it has memory."""
        assert GoogleADKTarget(FakeAgent(), "adk-bot").is_stateful() is True

    def test_bare_agent_documentation_mentions_the_agent_type(self):
        docs = GoogleADKTarget(FakeAgent(), "adk-bot").get_tool_documentation()
        assert "FakeAgent" in docs


class TestToolDocumentation:
    def test_stateful_runner_documentation(self, target):
        docs = target.get_tool_documentation()
        assert "Memory: Yes" in docs
        assert "ADK session id" in docs
        assert "send_message_to_target(message, conversation_id)" in docs

    def test_runner_without_a_session_service_is_honest(self):
        class NoSessionRunner:
            session_service = None

            async def run_async(self, **kwargs):  # pragma: no cover - not driven
                yield FakeEvent("hi")

        target = GoogleADKTarget(NoSessionRunner(), "adk-bot")
        docs = target.get_tool_documentation()
        assert "Memory: No" in docs
        assert "does not restore prior context" in docs

    def test_documentation_names_the_target(self, target):
        assert "My ADK agent" in target.get_tool_documentation()

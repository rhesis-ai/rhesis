"""Tests for PydanticAITarget."""

import asyncio

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from rhesis.penelope.targets.pydantic_ai import PydanticAITarget
from rhesis.sdk.targets import TargetResponse


@pytest.fixture
def agent():
    """Create a Pydantic AI agent backed by TestModel."""
    return Agent(TestModel(custom_output_text="hi there!"), name="my-agent")


SAMPLE_FILES = [
    {
        "filename": "image.png",
        "content_type": "image/png",
        "data": "iVBORw0KGgoAAAANSUhEUg==",
    },
]


class _FakeFileReference:
    def __init__(self, filename, content_type, content, extracted_text=None):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self.extracted_text = extracted_text

    def read_bytes(self):
        return self._content

    async def aread_bytes(self):
        return self._content


def test_target_initialization(agent):
    target = PydanticAITarget(agent, "test-target", "A test agent")

    assert target.agent is agent
    assert target.target_type == "pydantic_ai"
    assert target.target_id == "test-target"
    assert target.description == "A test agent"


def test_target_default_description(agent):
    target = PydanticAITarget(agent, "test-target")

    assert "test-target" in target.description


def test_target_rejects_none_agent():
    with pytest.raises(ValueError, match="Agent cannot be None"):
        PydanticAITarget(None, "test-target")


def test_target_rejects_empty_target_id(agent):
    with pytest.raises(ValueError, match="target_id cannot be empty"):
        PydanticAITarget(agent, "")


def test_target_rejects_agent_without_run_sync():
    class NotAnAgent:
        pass

    with pytest.raises(ValueError, match="run_sync"):
        PydanticAITarget(NotAnAgent(), "test-target")


def test_target_rejects_agent_without_run():
    class SyncOnlyAgent:
        def run_sync(self, *args, **kwargs):
            pass

    with pytest.raises(ValueError, match="run\\(\\)"):
        PydanticAITarget(SyncOnlyAgent(), "test-target")


def test_send_message_with_files(agent):
    target = PydanticAITarget(agent, "test-target")

    response = target.send_message("What is this?", files=SAMPLE_FILES)

    assert response.success is True
    assert response.content == "hi there!"


def test_send_message_with_files_passes_binary_content(agent):
    captured = {}
    original_run_sync = agent.run_sync

    def spy_run_sync(user_prompt, **kwargs):
        captured["user_prompt"] = user_prompt
        return original_run_sync(user_prompt, **kwargs)

    agent.run_sync = spy_run_sync
    target = PydanticAITarget(agent, "test-target")

    target.send_message("What is this?", files=SAMPLE_FILES)

    from pydantic_ai import BinaryContent

    assert captured["user_prompt"][0] == "What is this?"
    assert isinstance(captured["user_prompt"][1], BinaryContent)
    assert captured["user_prompt"][1].media_type == "image/png"


def test_a_send_message_with_files(agent):
    target = PydanticAITarget(agent, "test-target")

    response = asyncio.run(target.a_send_message("What is this?", files=SAMPLE_FILES))

    assert response.success is True
    assert response.content == "hi there!"


def test_send_message_with_file_reference_without_extracted_text(agent):
    target = PydanticAITarget(agent, "test-target")
    file_ref = _FakeFileReference("photo.png", "image/png", b"rawbytes")

    response = target.send_message("What is this?", files=[file_ref])

    assert response.success is True


def test_send_message_with_file_reference_extracted_text_used_as_text_part(agent):
    captured = {}
    original_run_sync = agent.run_sync

    def spy_run_sync(user_prompt, **kwargs):
        captured["user_prompt"] = user_prompt
        return original_run_sync(user_prompt, **kwargs)

    agent.run_sync = spy_run_sync
    target = PydanticAITarget(agent, "test-target")
    file_ref = _FakeFileReference(
        "doc.pdf", "application/pdf", b"unused", extracted_text="Hello from PDF"
    )

    target.send_message("Summarize", files=[file_ref])

    assert isinstance(captured["user_prompt"][1], str)
    assert "Hello from PDF" in captured["user_prompt"][1]


def test_a_send_message_with_file_reference_uses_aread_bytes(agent):
    target = PydanticAITarget(agent, "test-target")
    file_ref = _FakeFileReference("photo.png", "image/png", b"rawbytes")

    response = asyncio.run(target.a_send_message("What is this?", files=[file_ref]))

    assert response.success is True


def test_validate_configuration_valid(agent):
    target = PydanticAITarget(agent, "test-target")

    is_valid, error = target.validate_configuration()
    assert is_valid is True
    assert error is None


def test_send_message_success(agent):
    target = PydanticAITarget(agent, "test-target")

    response = target.send_message("Hello")

    assert isinstance(response, TargetResponse)
    assert response.success is True
    assert response.content == "hi there!"
    assert response.conversation_id == "default"
    assert response.metadata["input_sent"] == "Hello"
    assert response.metadata["agent_type"] == "Agent"


def test_send_message_uses_conversation_id(agent):
    target = PydanticAITarget(agent, "test-target")

    response = target.send_message("Hello", conversation_id="conv-1")

    assert response.conversation_id == "conv-1"


def test_send_message_empty_rejected(agent):
    target = PydanticAITarget(agent, "test-target")

    response = target.send_message("")

    assert response.success is False
    assert "Empty message" in response.error


def test_send_message_whitespace_only_rejected(agent):
    target = PydanticAITarget(agent, "test-target")

    response = target.send_message("   ")

    assert response.success is False


def test_send_message_multi_turn_accumulates_history(agent):
    target = PydanticAITarget(agent, "test-target")

    r1 = target.send_message("Hello", conversation_id="conv-1")
    r2 = target.send_message("How are you?", conversation_id="conv-1")

    assert r1.metadata["session_messages_count"] == 2
    assert r2.metadata["session_messages_count"] == 4


def test_send_message_separate_conversations_isolated(agent):
    target = PydanticAITarget(agent, "test-target")

    target.send_message("Hello", conversation_id="conv-1")
    target.send_message("Hello", conversation_id="conv-1")
    r = target.send_message("Hi", conversation_id="conv-2")

    assert r.metadata["session_messages_count"] == 2


def test_send_message_handles_exception(agent):
    def boom(*args, **kwargs):
        raise RuntimeError("model unavailable")

    agent.run_sync = boom
    target = PydanticAITarget(agent, "test-target")

    response = target.send_message("Hello")

    assert response.success is False
    assert "model unavailable" in response.error


def test_a_send_message_success(agent):
    target = PydanticAITarget(agent, "test-target")

    response = asyncio.run(target.a_send_message("Hello"))

    assert response.success is True
    assert response.content == "hi there!"


def test_a_send_message_empty_rejected(agent):
    target = PydanticAITarget(agent, "test-target")

    response = asyncio.run(target.a_send_message(""))

    assert response.success is False


def test_a_send_message_handles_exception(agent):
    async def boom(*args, **kwargs):
        raise RuntimeError("model unavailable")

    agent.run = boom
    target = PydanticAITarget(agent, "test-target")

    response = asyncio.run(target.a_send_message("Hello"))

    assert response.success is False
    assert "model unavailable" in response.error


def test_get_tool_documentation(agent):
    target = PydanticAITarget(agent, "test-target", "A test agent")

    doc = target.get_tool_documentation()

    assert "A test agent" in doc
    assert "Pydantic AI" in doc
    assert "send_message_to_target" in doc


def test_clear_session(agent):
    target = PydanticAITarget(agent, "test-target")

    target.send_message("Hello", conversation_id="conv-1")
    assert "conv-1" in target._session_histories

    target.clear_session("conv-1")
    assert "conv-1" not in target._session_histories


def test_clear_session_nonexistent_is_noop(agent):
    target = PydanticAITarget(agent, "test-target")

    target.clear_session("does-not-exist")

"""Tests for AutoGenTarget."""

from unittest.mock import MagicMock

import pytest

from rhesis.penelope.targets.autogen import AutoGenTarget


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.name = "assistant"
    agent.generate_reply.side_effect = lambda messages, **kwargs: f"Reply to: {messages[-1]['content']}"
    return agent


def test_autogen_target_initialization(mock_agent):
    target = AutoGenTarget(mock_agent, "bot-1", "Test bot")
    assert target.target_type == "autogen"
    assert target.target_id == "bot-1"
    assert target.agent == mock_agent


def test_autogen_target_rejects_missing_generate_reply():
    agent = MagicMock(spec=[])
    with pytest.raises(ValueError, match="generate_reply"):
        AutoGenTarget(agent, "bot-1")


def test_send_message_success(mock_agent):
    target = AutoGenTarget(mock_agent, "bot-1")
    response = target.send_message("Hello")

    assert response.success is True
    assert "Hello" in response.content
    assert response.conversation_id == "default"
    mock_agent.generate_reply.assert_called_once()


def test_send_message_empty():
    agent = MagicMock()
    agent.generate_reply = MagicMock()
    target = AutoGenTarget(agent, "bot-1")
    response = target.send_message("   ")

    assert response.success is False
    assert response.error == "Empty message"
    agent.generate_reply.assert_not_called()


def test_send_message_multi_turn(mock_agent):
    target = AutoGenTarget(mock_agent, "bot-1")
    first = target.send_message("Hello", conversation_id="session-1")
    second = target.send_message("Follow up", conversation_id="session-1")

    assert first.success is True
    assert second.success is True
    assert second.conversation_id == "session-1"
    assert mock_agent.generate_reply.call_count == 2

    second_call_messages = mock_agent.generate_reply.call_args_list[1].kwargs["messages"]
    assert len(second_call_messages) >= 3


def test_send_message_handles_exception(mock_agent):
    mock_agent.generate_reply.side_effect = RuntimeError("boom")
    target = AutoGenTarget(mock_agent, "bot-1")
    response = target.send_message("Hello")

    assert response.success is False
    assert "AutoGen error" in (response.error or "")


def test_clear_session(mock_agent):
    target = AutoGenTarget(mock_agent, "bot-1")
    target.send_message("Hello", conversation_id="session-1")
    target.clear_session("session-1")
    target.send_message("Again", conversation_id="session-1")

    first_messages = mock_agent.generate_reply.call_args_list[0].kwargs["messages"]
    second_messages = mock_agent.generate_reply.call_args_list[1].kwargs["messages"]
    assert len(first_messages) == 1
    assert len(second_messages) == 1
    assert first_messages[0]["content"] == "Hello"
    assert second_messages[0]["content"] == "Again"

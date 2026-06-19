"""Tests for GoogleADKTarget."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rhesis.penelope.targets.google_adk import GoogleADKTarget


@pytest.fixture
def mock_runner():
    runner = MagicMock()
    runner.run = MagicMock(return_value={"parts": [{"text": "ADK reply"}]})
    return runner


def test_google_adk_target_initialization(mock_runner):
    target = GoogleADKTarget(runner=mock_runner, target_id="adk-1", description="ADK bot")
    assert target.target_type == "google_adk"
    assert target.target_id == "adk-1"


def test_google_adk_target_rejects_missing_run():
    runner = MagicMock(spec=[])
    with pytest.raises(ValueError, match="run\\(\\)"):
        GoogleADKTarget(runner=runner, target_id="adk-1")


def test_send_message_success(mock_runner):
    target = GoogleADKTarget(runner=mock_runner, target_id="adk-1")
    response = target.send_message("Hello", conversation_id="session-1")

    assert response.success is True
    assert response.content == "ADK reply"
    assert response.conversation_id == "session-1"
    mock_runner.run.assert_called_once()


def test_send_message_async_runner():
    runner = MagicMock()
    runner.run = AsyncMock(return_value="async reply")
    target = GoogleADKTarget(runner=runner, target_id="adk-1")
    response = target.send_message("Hello", conversation_id="session-2")

    assert response.success is True
    assert response.content == "async reply"


def test_send_message_empty(mock_runner):
    target = GoogleADKTarget(runner=mock_runner, target_id="adk-1")
    response = target.send_message(" ")
    assert response.success is False
    mock_runner.run.assert_not_called()

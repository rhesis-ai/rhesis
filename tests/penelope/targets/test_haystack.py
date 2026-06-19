"""Tests for HaystackTarget."""

from unittest.mock import MagicMock

import pytest

from rhesis.penelope.targets.haystack import HaystackTarget


@pytest.fixture
def mock_pipeline():
    pipeline = MagicMock()
    pipeline.run.return_value = {"answer": "Haystack reply"}
    return pipeline


def test_haystack_target_initialization(mock_pipeline):
    target = HaystackTarget(mock_pipeline, "rag-1", "RAG pipeline")
    assert target.target_type == "haystack"
    assert target.target_id == "rag-1"


def test_haystack_target_rejects_missing_run():
    pipeline = MagicMock(spec=[])
    with pytest.raises(ValueError, match="run\\(\\)"):
        HaystackTarget(pipeline, "rag-1")


def test_send_message_success(mock_pipeline):
    target = HaystackTarget(mock_pipeline, "rag-1")
    response = target.send_message("What is NLP?")

    assert response.success is True
    assert response.content == "Haystack reply"
    mock_pipeline.run.assert_called_once_with({"query": "What is NLP?"})


def test_send_message_with_history(mock_pipeline):
    target = HaystackTarget(mock_pipeline, "rag-1", history_key="messages")
    first = target.send_message("Hello", conversation_id="s1")
    second = target.send_message("Follow up", conversation_id="s1")

    assert first.success and second.success
    second_call = mock_pipeline.run.call_args_list[1].args[0]
    assert "messages" in second_call
    assert len(second_call["messages"]) >= 3


def test_send_message_empty(mock_pipeline):
    target = HaystackTarget(mock_pipeline, "rag-1")
    response = target.send_message("  ")
    assert response.success is False
    mock_pipeline.run.assert_not_called()

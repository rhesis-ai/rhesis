"""Tests for HaystackTarget."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rhesis.penelope.targets.haystack import HaystackTarget


@pytest.fixture
def mock_pipeline():
    pipeline = MagicMock()
    pipeline.run.return_value = {"answer": "Haystack reply"}
    pipeline.run_async = AsyncMock(return_value={"answer": "Haystack async reply"})
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


def test_send_message_nested_component_inputs(mock_pipeline):
    target = HaystackTarget(
        mock_pipeline,
        "rag-1",
        input_mapping={"retriever": "query", "prompt_builder": "question"},
    )
    response = target.send_message("What is RAG?")

    assert response.success is True
    mock_pipeline.run.assert_called_once_with(
        {
            "retriever": {"query": "What is RAG?"},
            "prompt_builder": {"question": "What is RAG?"},
        }
    )


def test_send_message_with_run_inputs_override(mock_pipeline):
    target = HaystackTarget(mock_pipeline, "rag-1")
    response = target.send_message(
        "ignored",
        run_inputs={"retriever": {"query": "custom"}, "prompt": {"question": "custom"}},
    )

    assert response.success is True
    mock_pipeline.run.assert_called_once_with(
        {"retriever": {"query": "custom"}, "prompt": {"question": "custom"}}
    )


@pytest.mark.asyncio
async def test_a_send_message_uses_run_async(mock_pipeline):
    target = HaystackTarget(mock_pipeline, "rag-1")
    response = await target.a_send_message("Async question")

    assert response.success is True
    assert response.content == "Haystack async reply"
    mock_pipeline.run_async.assert_awaited_once()


def test_send_message_rejects_files(mock_pipeline):
    target = HaystackTarget(mock_pipeline, "rag-1")
    response = target.send_message("Hello", files=[{"filename": "doc.pdf"}])

    assert response.success is False
    assert "does not support file attachments" in (response.error or "")
    mock_pipeline.run.assert_not_called()


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

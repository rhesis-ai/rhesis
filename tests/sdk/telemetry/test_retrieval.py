"""Retrieval spans record their documents as a JSON list of texts."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from rhesis.telemetry.attributes import AIAttributes, AIEvents

from rhesis.sdk.telemetry.retrieval import document_text, documents_json, record_documents


def test_document_text_reads_each_framework_shape():
    assert document_text(SimpleNamespace(page_content="LangChain doc")) == "LangChain doc"
    assert document_text(SimpleNamespace(content="Haystack doc")) == "Haystack doc"
    assert document_text({"page_content": "dict doc"}) == "dict doc"
    assert document_text({"text": "text doc"}) == "text doc"
    assert document_text("plain doc") == "plain doc"


def test_document_text_falls_back_to_json_or_str():
    assert document_text({"id": 1}) == '{"id": 1}'
    assert document_text(42) == "42"


def test_documents_json_keeps_whole_documents():
    assert json.loads(documents_json(["one", "two"])) == ["one", "two"]


def test_an_empty_retrieval_records_an_empty_list():
    assert documents_json([]) == "[]"
    assert documents_json(None) == "[]"


def test_the_first_document_that_overflows_is_shortened_and_the_rest_dropped():
    recorded = documents_json(["a" * 10, "b" * 50, "c" * 10], limit=40)

    texts = json.loads(recorded)
    assert len(recorded) <= 40
    assert texts[0] == "a" * 10
    assert texts[1] and set(texts[1]) == {"b"}
    assert len(texts) == 2


def test_escapes_never_push_the_list_past_the_limit():
    recorded = documents_json(['"quoted"\n' * 20], limit=50)

    assert len(recorded) <= 50
    assert isinstance(json.loads(recorded), list)


def test_a_document_too_long_for_any_room_is_dropped():
    recorded = documents_json(["first", "x" * 100], limit=len('["first"]') + 1)

    assert json.loads(recorded) == ["first"]


def test_record_documents_adds_the_results_event():
    span = MagicMock()

    record_documents(span, [SimpleNamespace(page_content="doc")])

    span.add_event.assert_called_once_with(
        AIEvents.RETRIEVAL_RESULTS, {AIAttributes.COMPLETION_CONTENT: '["doc"]'}
    )


@pytest.fixture
def tracer():
    from rhesis.sdk.telemetry.tracer import Tracer

    with patch("rhesis.sdk.telemetry.tracer.get_tracer_provider"):
        return Tracer(api_key="key", project_id="project", environment="test", base_url="http://x")


def test_observe_retrieval_records_what_the_function_returned(tracer):
    span = MagicMock()
    span.attributes = {AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RETRIEVAL}

    tracer._capture_function_result(span, ["doc one", "doc two"])

    span.add_event.assert_called_once_with(
        AIEvents.RETRIEVAL_RESULTS, {AIAttributes.COMPLETION_CONTENT: '["doc one", "doc two"]'}
    )


@pytest.mark.parametrize(
    ("result", "recorded"),
    [
        (None, "[]"),
        ({"documents": ["doc one"]}, '["doc one"]'),
        ("one doc", '["one doc"]'),
    ],
)
def test_observe_retrieval_reads_documents_from_other_shapes(tracer, result, recorded):
    """Nothing found is an empty retrieval, not a document called "None"."""
    span = MagicMock()
    span.attributes = {AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RETRIEVAL}

    tracer._capture_function_result(span, result)

    span.add_event.assert_called_once_with(
        AIEvents.RETRIEVAL_RESULTS, {AIAttributes.COMPLETION_CONTENT: recorded}
    )


def test_other_spans_record_no_documents(tracer):
    span = MagicMock()
    span.attributes = {AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE}

    tracer._capture_function_result(span, ["doc"])

    span.add_event.assert_not_called()

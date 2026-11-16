"""The process-wide pre-call check runs before LiteLLM calls the provider."""

from __future__ import annotations

from typing import Any, List, Tuple
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.sdk.models import (
    LiteLLM,
    ModelCallRefused,
    get_default_precall_check,
    set_default_precall_check,
)


class _Refused(ModelCallRefused):
    pass


class _RefusedWithRetryableStatus(Exception):
    status_code = 503


@pytest.fixture(autouse=True)
def _uninstall():
    yield
    set_default_precall_check(None)


def _response(text: str = "ok") -> Mock:
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = text
    response.usage = None
    return response


def _refuse(model, request):
    raise _Refused("capped")


@pytest.fixture
def seen() -> List[Tuple[Any, Any]]:
    calls: List[Tuple[Any, Any]] = []

    def check(model, request):
        calls.append((model, request))

    set_default_precall_check(check)
    return calls


def test_get_returns_the_installed_check():
    set_default_precall_check(_refuse)
    assert get_default_precall_check() is _refuse


@patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
def test_generate_passes_the_model_and_what_it_will_send(mock_acompletion, seen):
    mock_acompletion.return_value = _response()
    llm = LiteLLM("provider/model")

    assert llm.generate("hi", system_prompt="be brief", max_tokens=50) == "ok"
    [(model, request)] = seen
    assert model is llm
    assert request["messages"] == [
        [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}]
    ]
    assert request["max_tokens"] == 50
    assert request["completions_per_prompt"] == 1
    assert request["response_format"] is None


@patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
def test_the_schema_is_passed_to_the_check(mock_acompletion, seen):
    mock_acompletion.return_value = _response('{"a": 1}')
    schema = {"type": "json_schema", "json_schema": {"name": "x", "schema": {"type": "object"}}}
    LiteLLM("provider/model").generate("hi", schema=schema)
    assert seen[0][1]["response_format"] is schema


@patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
def test_a_refusal_stops_the_call_and_is_not_retried(mock_acompletion):
    attempts = []

    def refuse(model, request):
        attempts.append(model)
        raise _Refused("capped")

    set_default_precall_check(refuse)
    llm = LiteLLM("provider/model")

    with pytest.raises(_Refused):
        llm.generate("hi")
    mock_acompletion.assert_not_called()
    assert len(attempts) == 1


@patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
def test_stream_runs_the_check(mock_acompletion):
    set_default_precall_check(_refuse)
    llm = LiteLLM("provider/model")

    with pytest.raises(_Refused):
        llm.generate("hi", stream=True)
    mock_acompletion.assert_not_called()


@patch("rhesis.sdk.models.providers.litellm.batch_completion")
def test_generate_batch_passes_every_prompt(mock_batch, seen):
    mock_batch.return_value = [_response("a"), _response("b")]
    llm = LiteLLM("provider/model")

    llm.generate_batch(["a", "b"], n=1)
    [(_, request)] = seen
    assert request["messages"] == [
        [{"role": "user", "content": "a"}],
        [{"role": "user", "content": "b"}],
    ]


@patch("rhesis.sdk.models.providers.litellm.batch_completion")
def test_generate_batch_runs_the_check_first(mock_batch):
    set_default_precall_check(_refuse)
    llm = LiteLLM("provider/model")

    with pytest.raises(_Refused):
        llm.generate_batch(["a", "b"])
    mock_batch.assert_not_called()


@patch("rhesis.sdk.models.providers.litellm.batch_completion")
def test_generate_batch_without_a_check(mock_batch):
    mock_batch.return_value = [_response("a")]
    llm = LiteLLM("provider/model")

    assert llm.generate_batch(["a"]) == ["a"]


def test_a_retryable_status_on_the_refusal_would_be_retried():
    """Why the docstring says to raise without a retryable status_code."""
    from rhesis.sdk.models.utils import _is_retryable_exception

    assert _is_retryable_exception(_RefusedWithRetryableStatus())
    assert not _is_retryable_exception(_Refused())


@patch("litellm.completion")
def test_the_extractor_adapter_is_checked_and_reports_usage(mock_completion, seen):
    """MarkItDown's direct litellm call goes through the same hook and usage sink."""
    from rhesis.sdk.services.extractor import _MarkItDownModelAdapter

    response = _response("a cat")
    response.usage = {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105}
    mock_completion.return_value = response
    llm = LiteLLM("provider/model")
    emitted = []
    llm.on_usage = emitted.append

    messages = [{"role": "user", "content": "describe"}]
    _MarkItDownModelAdapter(llm).chat.completions.create(model="x", messages=messages)

    assert seen[0][1]["messages"] == [messages]
    assert emitted[0]["total_tokens"] == 105


@patch("litellm.completion")
def test_the_extractor_adapter_refusal_skips_the_call(mock_completion):
    from rhesis.sdk.services.extractor import _MarkItDownModelAdapter

    set_default_precall_check(_refuse)
    with pytest.raises(_Refused):
        _MarkItDownModelAdapter(LiteLLM("provider/model")).chat.completions.create(
            model="x", messages=[]
        )
    mock_completion.assert_not_called()

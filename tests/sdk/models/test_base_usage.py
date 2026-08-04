"""Tests for BaseLLM's token-usage normalization and emission.

This is the boundary where a provider's raw ``usage`` payload becomes a
:class:`TokenUsage` for accrual callbacks. Every provider dialect is
resolved here, so consumers downstream (notably the backend's
MODEL_TOKENS callback) never parse token counts themselves.
"""

from __future__ import annotations

from typing import Any, List

import pytest

from rhesis.sdk.models.base import BaseLLM, TokenUsage, _normalize_usage


class _StubLLM(BaseLLM):
    """Minimal concrete BaseLLM -- load_model/generate_batch are abstract."""

    def load_model(self, *args, **kwargs):
        return self

    def generate_batch(self, *args, **kwargs):
        return []


@pytest.fixture
def emitted() -> List[Any]:
    return []


@pytest.fixture
def model(emitted):
    return _StubLLM("stub-model", on_usage=emitted.append)


class TestNormalizeUsage:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ({"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}, (10, 20, 30)),
            ({"input_tokens": 12, "output_tokens": 18, "total_tokens": 30}, (12, 18, 30)),
            ({"prompt_token_count": 15, "candidates_token_count": 25}, (15, 25, 40)),
            ({"promptTokenCount": 3, "candidatesTokenCount": 4}, (3, 4, 7)),
        ],
        ids=["openai-legacy", "openai-responses", "gemini", "gemini-camel"],
    )
    def test_resolves_provider_dialects(self, raw, expected):
        result = _normalize_usage(raw)

        assert result == TokenUsage(
            input_tokens=expected[0], output_tokens=expected[1], total_tokens=expected[2]
        )

    def test_derives_total_when_provider_omits_it(self):
        """The case the old hand-rolled `usage["total_tokens"]` read dropped
        on the floor."""
        assert _normalize_usage({"prompt_tokens": 7, "completion_tokens": 5})["total_tokens"] == 12

    def test_is_idempotent(self):
        """Already-normalized input must survive a second pass unchanged --
        _emit_usage_batch relies on this when re-normalizing its own sums."""
        once = _normalize_usage({"prompt_tokens": 10, "completion_tokens": 20})

        assert _normalize_usage(once) == once

    @pytest.mark.parametrize("raw", [None, {}, {"total_tokens": 0}, {"unrelated": "value"}])
    def test_returns_none_when_there_is_nothing_to_report(self, raw):
        assert _normalize_usage(raw) is None


class TestEmitUsage:
    def test_emits_normalized_counts(self, model, emitted):
        model._emit_usage({"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})

        assert emitted == [TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)]

    @pytest.mark.parametrize("raw", [None, {}, {"total_tokens": 0}])
    def test_skips_empty_payloads(self, model, emitted, raw):
        model._emit_usage(raw)

        assert emitted == []

    def test_no_callback_configured_is_a_noop(self):
        _StubLLM("stub-model")._emit_usage({"total_tokens": 5})  # must not raise

    def test_callback_exception_never_escapes(self):
        """A broken accrual callback must not break the LLM call that
        produced the usage."""

        def boom(_usage):
            raise RuntimeError("accrual backend down")

        model = _StubLLM("stub-model", on_usage=boom)

        model._emit_usage({"total_tokens": 5})  # must not raise


class TestEmitUsageBatch:
    def test_sums_across_items_and_emits_once(self, model, emitted):
        model._emit_usage_batch(
            [
                {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            ]
        )

        assert emitted == [TokenUsage(input_tokens=11, output_tokens=22, total_tokens=33)]

    def test_counts_items_that_omit_total_tokens(self, model, emitted):
        """Per-item normalization, not a raw `total_tokens` read: an item
        reporting only prompt/completion counts still contributes."""
        model._emit_usage_batch(
            [
                {"total_tokens": 30, "prompt_tokens": 10, "completion_tokens": 20},
                {"prompt_tokens": 4, "completion_tokens": 6},
            ]
        )

        assert emitted[0]["total_tokens"] == 40

    def test_ignores_items_with_no_usage(self, model, emitted):
        model._emit_usage_batch([None, {"total_tokens": 5}, {}])

        assert emitted == [TokenUsage(input_tokens=0, output_tokens=0, total_tokens=5)]

    def test_batch_with_no_usage_at_all_emits_nothing(self, model, emitted):
        model._emit_usage_batch([None, {}, {"total_tokens": 0}])

        assert emitted == []

    def test_no_callback_configured_is_a_noop(self):
        _StubLLM("stub-model")._emit_usage_batch([{"total_tokens": 5}])  # must not raise

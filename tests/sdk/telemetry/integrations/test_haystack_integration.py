"""Tests for Haystack auto-instrumentation integration."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.telemetry.integrations.haystack import (
    HaystackIntegration,
    HaystackPatchState,
    _wrap_pipeline_run,
)


@pytest.fixture(autouse=True)
def reset_patch_state():
    HaystackPatchState.reset()
    yield
    HaystackPatchState.reset()


def test_wrap_pipeline_run_traces_execution():
    original = MagicMock(return_value={"answer": "done"})
    pipeline = MagicMock()
    pipeline.metadata = {"name": "qa-pipeline"}

    wrapped = _wrap_pipeline_run(original)
    result = wrapped(pipeline, {"query": "hello"})

    assert result == {"answer": "done"}
    original.assert_called_once_with(pipeline, {"query": "hello"})


def test_enable_patches_pipeline_run(monkeypatch):
    class FakePipeline:
        def run(self, data=None, *args, **kwargs):
            return {"answer": "ok"}

    fake_haystack = MagicMock()
    fake_haystack.Pipeline = FakePipeline
    fake_tracing = MagicMock()
    fake_tracing.enable_tracing = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "haystack", fake_haystack)
    monkeypatch.setitem(__import__("sys").modules, "haystack.tracing", fake_tracing)

    with patch(
        "rhesis.sdk.telemetry.integrations.haystack._enable_haystack_tracing",
        side_effect=ImportError("tracing unavailable"),
    ):
        integration = HaystackIntegration()
        assert integration.enable() is True
        assert HaystackPatchState.is_done() is True


def test_disable_restores_pipeline(monkeypatch):
    class FakePipeline:
        def run(self, data=None, *args, **kwargs):
            return {"answer": "ok"}

    fake_haystack = MagicMock()
    fake_haystack.Pipeline = FakePipeline
    monkeypatch.setitem(__import__("sys").modules, "haystack", fake_haystack)

    with patch(
        "rhesis.sdk.telemetry.integrations.haystack._enable_haystack_tracing",
        return_value="tracer",
    ):
        integration = HaystackIntegration()
        integration.enable()
        integration.disable()

    assert integration.enabled is False
    assert HaystackPatchState.is_done() is False

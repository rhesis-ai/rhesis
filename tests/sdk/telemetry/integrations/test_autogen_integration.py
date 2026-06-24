"""Tests for AutoGen auto-instrumentation integration."""

from unittest.mock import MagicMock

import pytest

from rhesis.sdk.telemetry.integrations.autogen import (
    AutoGenIntegration,
    AutoGenPatchState,
    _extract_model_from_agent,
    _wrap_generate_reply,
)


@pytest.fixture(autouse=True)
def reset_patch_state():
    """Reset AutoGen patching state before each test."""
    AutoGenPatchState.reset()
    yield
    AutoGenPatchState.reset()


@pytest.fixture
def integration():
    return AutoGenIntegration()


def test_extract_model_from_agent():
    agent = MagicMock()
    agent.llm_config = {"config_list": [{"model": "gpt-4o-mini"}]}
    assert _extract_model_from_agent(agent) == "gpt-4o-mini"


def test_wrap_generate_reply_traces_call():
    original = MagicMock(return_value="assistant reply")
    agent = MagicMock()
    agent.name = "assistant"
    agent.llm_config = {"config_list": [{"model": "gpt-4o"}]}

    wrapped = _wrap_generate_reply(original)
    result = wrapped(agent, messages=[{"role": "user", "content": "hi"}])

    assert result == "assistant reply"
    original.assert_called_once()


def test_enable_patches_conversable_agent(monkeypatch):
    class FakeConversableAgent:
        def generate_reply(self, *args, **kwargs):
            return "ok"

    fake_autogen = MagicMock()
    fake_autogen.ConversableAgent = FakeConversableAgent
    monkeypatch.setitem(__import__("sys").modules, "autogen", fake_autogen)

    integration = AutoGenIntegration()
    assert integration.enable() is True
    assert integration.enabled is True
    assert AutoGenPatchState.is_done() is True


def test_disable_restores_original(monkeypatch):
    class FakeConversableAgent:
        original_called = False

        def generate_reply(self, *args, **kwargs):
            self.original_called = True
            return "original"

    fake_autogen = MagicMock()
    fake_autogen.ConversableAgent = FakeConversableAgent
    monkeypatch.setitem(__import__("sys").modules, "autogen", fake_autogen)

    integration = AutoGenIntegration()
    integration.enable()
    integration.disable()

    assert integration.enabled is False
    assert AutoGenPatchState.is_done() is False


def test_enable_when_not_installed():
    class NotInstalledIntegration(AutoGenIntegration):
        def is_installed(self) -> bool:
            return False

    assert NotInstalledIntegration().enable() is False


def test_set_token_attributes_records_zero_counts():
    from opentelemetry.sdk.trace import TracerProvider

    from rhesis.sdk.telemetry.attributes import AIAttributes
    from rhesis.sdk.telemetry.integrations.tracing_helpers import set_token_attributes

    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    span = tracer.start_span("test")
    set_token_attributes(
        span,
        {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    attrs = dict(span.attributes or {})
    span.end()

    assert attrs[AIAttributes.LLM_TOKENS_INPUT] == 0
    assert attrs[AIAttributes.LLM_TOKENS_OUTPUT] == 0
    assert attrs[AIAttributes.LLM_TOKENS_TOTAL] == 0

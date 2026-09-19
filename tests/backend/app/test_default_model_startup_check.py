"""A deployment that cannot build its own default models says so at boot.

Before this, the first and only signal was a 500 on the first execute
(#2671), by which point whoever set the environment was long gone. The
check warns rather than raises: a deployment that never resolves a model
still has to start.
"""

from __future__ import annotations

import logging

import pytest

from rhesis.backend.app.utils import user_model_utils


@pytest.fixture(autouse=True)
def _rerun_the_check():
    """The check is once-per-process, so clear the flag around every test."""
    user_model_utils._default_models_checked = False
    yield
    user_model_utils._default_models_checked = False


def _warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_warns_once_per_unbuildable_setting(monkeypatch, caplog):
    def boom(model_string, **kwargs):
        raise ValueError("RHESIS_API_KEY is not set")

    monkeypatch.setattr(user_model_utils, "get_model", boom)

    with caplog.at_level(logging.WARNING, logger=user_model_utils.__name__):
        user_model_utils.warn_on_unbuildable_default_models()

    messages = _warnings(caplog)
    assert len(messages) == len(user_model_utils._DEFAULT_MODEL_SETTINGS)
    for env_var, _field, _model_type in user_model_utils._DEFAULT_MODEL_SETTINGS:
        assert any(env_var in message for message in messages)
    assert all("RHESIS_API_KEY is not set" in message for message in messages)


def test_a_provider_missing_an_optional_dependency_does_not_take_startup_down(monkeypatch, caplog):
    """huggingface raises ImportError without torch. A boot diagnostic that
    crashed the app would be worse than the problem it reports."""

    def boom(model_string, **kwargs):
        raise ImportError("No module named 'torch'")

    monkeypatch.setattr(user_model_utils, "get_model", boom)

    with caplog.at_level(logging.WARNING, logger=user_model_utils.__name__):
        user_model_utils.warn_on_unbuildable_default_models()

    assert len(_warnings(caplog)) == len(user_model_utils._DEFAULT_MODEL_SETTINGS)


def test_silent_when_every_default_builds(monkeypatch, caplog):
    monkeypatch.setattr(user_model_utils, "get_model", lambda model_string, **kwargs: object())

    with caplog.at_level(logging.WARNING, logger=user_model_utils.__name__):
        user_model_utils.warn_on_unbuildable_default_models()

    assert _warnings(caplog) == []


def test_runs_once_per_process(monkeypatch):
    """The test suite starts a fresh app lifespan per test; without this the
    whole check, and its warnings, would repeat several hundred times a run."""
    calls = []

    monkeypatch.setattr(
        user_model_utils, "get_model", lambda model_string, **kwargs: calls.append(model_string)
    )

    user_model_utils.warn_on_unbuildable_default_models()
    user_model_utils.warn_on_unbuildable_default_models()

    assert len(calls) == len(user_model_utils._DEFAULT_MODEL_SETTINGS)


def test_checks_each_setting_with_the_right_model_type(monkeypatch):
    """The embedding default is a different SDK type; asking for a language
    model would report a working embedder as broken."""
    seen = []

    def record(model_string, **kwargs):
        seen.append((model_string, kwargs.get("model_type")))

    monkeypatch.setattr(user_model_utils, "get_model", record)

    user_model_utils.warn_on_unbuildable_default_models()

    settings = user_model_utils.get_model_settings()
    assert seen == [
        (getattr(settings, field), model_type)
        for _env_var, field, model_type in user_model_utils._DEFAULT_MODEL_SETTINGS
    ]


def test_the_worker_runs_the_same_check_at_boot(monkeypatch):
    """A metric evaluation resolves a model on the worker, so a worker whose
    environment differs from the API's has to report its own gap."""
    from rhesis.backend.celery import signals

    calls = []
    monkeypatch.setattr(user_model_utils, "get_model", lambda m, **kw: calls.append(m))

    signals.report_unbuildable_default_models()

    assert len(calls) == len(user_model_utils._DEFAULT_MODEL_SETTINGS)

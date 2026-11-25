"""LiteLLM and Penelope log through the root handlers, once, in our format."""

import logging

import pytest

from rhesis.backend.logging.logging_config import (
    _GeminiSamplingDeprecationFilter,
    _route_library_loggers,
)


@pytest.fixture
def restore_library_loggers():
    names = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy", "rhesis.penelope")
    saved = {
        name: (
            list(logging.getLogger(name).handlers),
            list(logging.getLogger(name).filters),
            logging.getLogger(name).propagate,
        )
        for name in names
    }
    yield
    for name, (handlers, filters, propagate) in saved.items():
        target = logging.getLogger(name)
        target.handlers[:] = handlers
        target.filters[:] = filters
        target.propagate = propagate


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord("LiteLLM", logging.WARNING, __file__, 1, message, None, None)


def test_library_loggers_lose_their_own_handlers(restore_library_loggers):
    logging.getLogger("LiteLLM").addHandler(logging.StreamHandler())

    _route_library_loggers()

    litellm_logger = logging.getLogger("LiteLLM")
    assert litellm_logger.handlers == []
    assert litellm_logger.propagate is True
    penelope_logger = logging.getLogger("rhesis.penelope")
    assert [type(h) for h in penelope_logger.handlers] == [logging.NullHandler]
    assert penelope_logger.propagate is True


def test_penelope_config_keeps_the_routing(restore_library_loggers):
    """Penelope adds a stderr handler only to a logger without one."""
    from rhesis.penelope.config import PenelopeConfig

    _route_library_loggers()
    PenelopeConfig._apply_logging_config()

    penelope_logger = logging.getLogger("rhesis.penelope")
    assert [type(h) for h in penelope_logger.handlers] == [logging.NullHandler]
    assert penelope_logger.propagate is True


def test_gemini_sampling_notice_is_dropped_and_nothing_else():
    drop = _GeminiSamplingDeprecationFilter()

    assert not drop.filter(
        _record(
            "DeprecationWarning: `temperature`, `top_p`, and `top_k` continue to function "
            "for Gemini 3+ (%s) but are planned for removal in a future release."
        )
    )
    assert drop.filter(_record("LoggingWorker error: something else"))


def test_eager_load_warning_fires_once_per_model(caplog, monkeypatch):
    from rhesis.backend.app.utils import query_utils

    monkeypatch.setattr(query_utils, "_warned_eager_load_models", set())
    builder = query_utils.QueryBuilder.__new__(query_utils.QueryBuilder)
    builder.model = type("Model", (), {})
    builder._eager_load_count = query_utils._MAX_EAGER_LOADS_WARN

    with caplog.at_level(logging.WARNING, logger=query_utils.logger.name):
        builder._maybe_warn_load_count()
        builder._maybe_warn_load_count()

    assert sum("eager loads" in r.getMessage() for r in caplog.records) == 1

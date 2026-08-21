"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from haystack import tracing
from opentelemetry import context as otel_context

from tests import integrations
from tests.mocks import MockChatGenerator, make_pipeline

__all__ = ["MockChatGenerator", "make_pipeline"]


def _integration_params() -> list[pytest.param]:
    """One param per integration, skipping any whose package is not installed.

    Upstream ``rhesis-haystack`` is not a declared dependency (its path source does not resolve
    from every checkout), so those params normally skip until it is installed by hand.
    """
    return [
        pytest.param(
            "native",
            marks=pytest.mark.skipif(
                not integrations.NATIVE_INSTALLED,
                reason=f"{integrations.NATIVE_MODULE} is not installed",
            ),
        ),
        pytest.param(
            "upstream",
            marks=pytest.mark.skipif(
                not integrations.UPSTREAM_INSTALLED,
                reason=(
                    f"{integrations.UPSTREAM_MODULE} is not installed; "
                    "uv pip install -e <path>/haystack-core-integrations/integrations/rhesis"
                ),
            ),
        ),
    ]


@pytest.fixture(params=_integration_params(), ids=lambda name: name)
def integration(request) -> integrations.Integration:
    """The Haystack tracing integration under test, one param per installed integration."""
    return integrations.load(request.param)


@pytest.fixture(autouse=True)
def isolate_otel_context():
    """Give each test a fresh OpenTelemetry context.

    A test that leaves a span attached leaves it as the current one, and the next test's "root"
    span then nests under it and inherits its trace id — an order-dependent failure that only
    shows up once the whole file runs. Running two integrations in one session doubles the risk.
    """
    token = otel_context.attach(otel_context.Context())
    yield
    otel_context.detach(token)


@pytest.fixture(autouse=True)
def reset_global_tracer():
    """Undo Haystack's process-wide tracer registration after each test."""
    previous_content_tracing = tracing.tracer.is_content_tracing_enabled
    yield
    tracing.disable_tracing()
    tracing.tracer.is_content_tracing_enabled = previous_content_tracing

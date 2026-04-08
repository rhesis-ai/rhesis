"""Data-level tests for Trace metric_scope membership (telemetry evaluation).

These tests validate the same list-membership semantics used by
``_load_trace_scoped_metrics`` in the evaluate task module, but operate
on plain Python lists rather than requiring a live database.
"""

import pytest

from rhesis.backend.app.schemas.metric import MetricScope


def _trace_in_scope(scope):
    """Same membership semantics used in _load_trace_scoped_metrics SQL filter."""
    if scope is None:
        return False
    return MetricScope.TRACE.value in scope


@pytest.mark.unit
class TestTraceMetricScopeFiltering:
    """Tests that Trace scope is detected via list membership on metric_scope values."""

    def test_trace_in_scope(self):
        scope = [MetricScope.TRACE.value, MetricScope.SINGLE_TURN.value]
        assert MetricScope.TRACE.value in scope

    def test_trace_and_single_turn_order_independent(self):
        a = [MetricScope.TRACE.value, MetricScope.SINGLE_TURN.value]
        b = [MetricScope.SINGLE_TURN.value, MetricScope.TRACE.value]
        assert (MetricScope.TRACE.value in a) is True
        assert (MetricScope.TRACE.value in b) is True
        assert (MetricScope.TRACE.value in a) == (MetricScope.TRACE.value in b)

    def test_trace_alone_matches(self):
        scope = [MetricScope.TRACE.value]
        assert MetricScope.TRACE.value in scope

    def test_no_trace_excluded(self):
        scope = [MetricScope.SINGLE_TURN.value]
        assert MetricScope.TRACE.value not in scope

    def test_trace_and_multi_turn(self):
        scope = [MetricScope.TRACE.value, MetricScope.MULTI_TURN.value]
        assert MetricScope.TRACE.value in scope
        assert MetricScope.MULTI_TURN.value in scope

    def test_empty_scope(self):
        scope = []
        assert MetricScope.TRACE.value not in scope

    def test_none_scope(self):
        scope = None
        assert _trace_in_scope(scope) is False

    def test_metric_scope_values_are_strings(self):
        """Ensure enum str mixin allows direct use in JSON lists."""
        assert MetricScope.TRACE == "Trace"
        assert MetricScope.SINGLE_TURN == "Single-Turn"
        assert MetricScope.MULTI_TURN == "Multi-Turn"

"""A metric cannot be created without a scope.

Execution filters metrics by scope, so an absent or empty `metric_scope` means the
metric is never evaluated by any path and reports no error. Enforcing it in
`MetricCreate` covers every writer that goes through the API: the UI, the SDK, the
MCP `create_metric` tool, and the Architect agent (which calls the same endpoint).
The `metric` table carries a matching CHECK constraint as the backstop for anything
that bypasses the API.
"""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.metric import (
    MetricCreate,
    MetricScope,
    MetricUpdate,
)


def _valid_payload(**overrides):
    """A numeric metric that satisfies every other MetricCreate rule."""
    payload = dict(
        name="Faithfulness",
        evaluation_prompt="Judge whether the response is faithful to the context.",
        score_type="numeric",
        min_score=0.0,
        max_score=1.0,
        threshold=0.5,
        metric_scope=[MetricScope.SINGLE_TURN],
    )
    payload.update(overrides)
    return payload


@pytest.mark.unit
class TestMetricCreateRequiresScope:
    def test_valid_scope_is_accepted(self):
        metric = MetricCreate(**_valid_payload())
        assert metric.metric_scope == [MetricScope.SINGLE_TURN]

    def test_omitted_scope_is_rejected(self):
        payload = _valid_payload()
        del payload["metric_scope"]

        with pytest.raises(ValidationError) as exc_info:
            MetricCreate(**payload)

        assert "metric_scope" in str(exc_info.value)

    def test_empty_scope_is_rejected(self):
        with pytest.raises(ValidationError):
            MetricCreate(**_valid_payload(metric_scope=[]))

    def test_null_scope_is_rejected(self):
        with pytest.raises(ValidationError):
            MetricCreate(**_valid_payload(metric_scope=None))

    def test_invalid_scope_value_is_rejected(self):
        with pytest.raises(ValidationError):
            MetricCreate(**_valid_payload(metric_scope=["Sometimes"]))

    @pytest.mark.parametrize(
        "scope",
        [
            [MetricScope.MULTI_TURN],
            [MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN],
            ["Multi-Turn"],
        ],
    )
    def test_accepted_scope_shapes(self, scope):
        assert MetricCreate(**_valid_payload(metric_scope=scope)).metric_scope


@pytest.mark.unit
class TestMetricUpdateScope:
    def test_omitting_scope_is_allowed(self):
        """None means "not being updated" on a partial update."""
        assert MetricUpdate(name="Renamed").metric_scope is None

    def test_scope_cannot_be_emptied(self):
        """Clearing the scope would silently disable the metric."""
        with pytest.raises(ValidationError) as exc_info:
            MetricUpdate(metric_scope=[])

        assert "metric_scope cannot be empty" in str(exc_info.value)

    def test_scope_can_be_changed(self):
        updated = MetricUpdate(metric_scope=[MetricScope.MULTI_TURN])
        assert updated.metric_scope == [MetricScope.MULTI_TURN]

"""What a synced SDK metric's declared parameters say about the inputs it needs."""

from types import SimpleNamespace

from rhesis.backend.app.services.connector.handlers.metric_sync import _update_existing_metric


def _synced(parameters):
    metric = SimpleNamespace(
        name="m",
        description="",
        score_type="numeric",
        evaluation_examples=None,
        ground_truth_required=None,
        context_required=None,
    )
    _update_existing_metric(metric, {"parameters": parameters}, {})
    return metric


def test_declaring_expectations_marks_the_metric_as_needing_a_reference():
    assert _synced(["output", "expectations"]).ground_truth_required is True
    assert _synced(["input", "output"]).ground_truth_required is False


def test_context_is_never_required_since_it_comes_from_the_trace():
    assert _synced(["output", "trace"]).context_required is False

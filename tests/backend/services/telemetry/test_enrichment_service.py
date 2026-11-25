"""
Tests for EnrichmentService: storing spans and queueing their turn evaluations.

Spans are enriched as they are stored (span_storage, tested in test_span_storage.py);
what this service still decides is which evaluations to queue, and it meters spans
from the endpoint invoker.
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.telemetry.enrichment import (
    EnrichmentService,
    build_turn_evaluation,
)

MODULE = "rhesis.backend.app.services.telemetry.enrichment.service"
STORE = "rhesis.backend.app.services.telemetry.span_storage.store_spans"
WITH_METRICS = {"metric_ids": ["m1"]}


def _spans(specs):
    """Mock stored spans from (trace_id, db_id, parent_span_id) tuples."""
    spans = []
    for trace_id, db_id, parent in specs:
        span = Mock()
        span.trace_id = trace_id
        span.id = db_id
        span.parent_span_id = parent
        span.attributes = {}
        spans.append(span)
    return spans


@pytest.fixture
def service():
    return EnrichmentService(Mock(spec=Session))


@pytest.fixture
def config():
    with patch(f"{MODULE}.project_trace_metrics_config", return_value=WITH_METRICS) as cfg:
        yield cfg


@pytest.mark.unit
class TestEnqueueEvaluation:
    def test_queues_the_turn_evaluation(self, service):
        signature = Mock()
        signature.apply_async.return_value = Mock(id="task-1")
        with patch(f"{MODULE}.build_turn_evaluation", return_value=signature) as build:
            assert service.enqueue_evaluation("t1", "p1", "o1", root_span_id="r1") is True

        build.assert_called_once_with("t1", "p1", "o1", root_span_id="r1")
        signature.apply_async.assert_called_once()

    def test_broker_down_skips_evaluation_and_never_runs_it_in_process(self, service):
        import redis.exceptions

        with (
            patch(
                f"{MODULE}.build_turn_evaluation",
                side_effect=redis.exceptions.ConnectionError("Redis down"),
            ),
            patch(f"{MODULE}.logger") as logger,
        ):
            assert service.enqueue_evaluation("t1", "p1", "o1", root_span_id="r1") is False

        assert "skipped" in logger.warning.call_args.args[0]


@pytest.mark.unit
class TestDispatchForSpans:
    def test_one_evaluation_per_root_span(self, service, config):
        stored = _spans(
            [("T1", "root-1", None), ("T1", "child-1", "root-1"), ("T1", "root-2", None)]
        )
        with patch.object(service, "enqueue_evaluation", return_value=True) as enqueue:
            assert service.dispatch_for_spans(stored, "p1", "o1") == (2, 0)

        assert {c.kwargs["root_span_id"] for c in enqueue.call_args_list} == {"root-1", "root-2"}

    def test_child_only_batches_queue_nothing(self, service, config):
        # Their trace was enriched when they were stored; there is no turn to evaluate.
        stored = _spans([("T2", "child-only", "some-parent")])
        with patch.object(service, "enqueue_evaluation") as enqueue:
            assert service.dispatch_for_spans(stored, "p1", "o1") == (0, 0)

        enqueue.assert_not_called()
        config.assert_not_called()

    @pytest.mark.parametrize(
        "project_config",
        [None, {}, {"metric_ids": []}, {"metric_ids": ["m1"], "enabled": False}],
    )
    def test_nothing_is_queued_for_a_project_without_trace_metrics(self, service, project_config):
        stored = _spans([("T1", "root-1", None)])
        with (
            patch(f"{MODULE}.project_trace_metrics_config", return_value=project_config),
            patch.object(service, "enqueue_evaluation") as enqueue,
        ):
            assert service.dispatch_for_spans(stored, "p1", "o1") == (0, 0)

        enqueue.assert_not_called()

    def test_counts_what_could_not_be_queued(self, service, config):
        stored = _spans([("T1", "root-1", None), ("T2", "root-2", None)])
        with patch.object(service, "enqueue_evaluation", side_effect=[True, False]):
            assert service.dispatch_for_spans(stored, "p1", "o1") == (1, 1)


@pytest.mark.unit
class TestBuildTurnEvaluation:
    def test_is_the_turn_task_with_its_root_span(self):
        sig = build_turn_evaluation("t1", "p1", "o1", root_span_id="span-db-1")

        assert sig.task == "rhesis.backend.jobs.telemetry.evaluate.evaluate_turn_trace_metrics"
        assert sig.args == ("t1", "p1", "o1")
        assert sig.kwargs == {"root_span_id": "span-db-1"}


@pytest.mark.unit
class TestCreateAndEnrichSpans:
    """Spans the invoker stores are metered, then their turns queued for evaluation."""

    def test_accrues_the_number_of_stored_spans(self, service, config):
        stored = _spans([("T1", "r1", None), ("T2", "r2", None), ("T3", "r3", None)])
        with (
            patch(STORE, return_value=stored),
            patch.object(service, "enqueue_evaluation", return_value=True),
            patch(f"{MODULE}.usage_coalescer.add") as accrual,
        ):
            stored, queued, not_queued = service.create_and_enrich_spans([], "org-1", "proj-1")

        assert (len(stored), queued, not_queued) == (3, 3, 0)
        org_id, resource, amount = accrual.call_args.args
        assert (org_id, str(resource), amount) == ("org-1", "tracing_spans", 3)

    def test_spans_made_from_a_reported_response_are_not_metered(self, service, config):
        """Tool calls and context a response reported are Rhesis's derivation."""
        stored = _spans([("T1", "r1", None), ("T1", "c1", "r1"), ("T1", "c2", "r1")])
        stored[1].attributes = {"rhesis.span.source": "reported"}
        stored[2].attributes = {"rhesis.span.source": "reported"}
        with (
            patch(STORE, return_value=stored),
            patch.object(service, "enqueue_evaluation", return_value=True),
            patch(f"{MODULE}.usage_coalescer.add") as accrual,
        ):
            service.create_and_enrich_spans([], "org-1", "proj-1")

        assert accrual.call_args.args[2] == 1

    def test_nothing_stored_means_nothing_metered_or_queued(self, service, config):
        with (
            patch(STORE, return_value=[]),
            patch.object(service, "enqueue_evaluation") as enqueue,
            patch(f"{MODULE}.usage_coalescer.add") as accrual,
        ):
            assert service.create_and_enrich_spans([], "org-1", "proj-1") == ([], 0, 0)

        accrual.assert_not_called()
        enqueue.assert_not_called()

    def test_accrues_even_if_queueing_fails(self, service, config):
        """The spans are stored and billable whatever happens to their evaluation."""
        with (
            patch(STORE, return_value=_spans([("T1", "r1", None), ("T1", "c1", "r1")])),
            patch.object(service, "enqueue_evaluation", side_effect=RuntimeError("broker down")),
            patch(f"{MODULE}.usage_coalescer.add") as accrual,
        ):
            with pytest.raises(RuntimeError):
                service.create_and_enrich_spans([], "org-1", "proj-1")

        assert accrual.call_args.args[2] == 2

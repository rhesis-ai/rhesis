"""Which metrics a project's traces are evaluated with (``_load_project_trace_metrics``)."""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.jobs.telemetry.evaluate import _load_project_trace_metrics
from tests.backend.routes.fixtures.data_factories import MetricDataFactory


def _metric(db: Session, org_id: str, user_id: str, scope: list[str]) -> models.Metric:
    metric = models.Metric(**MetricDataFactory.orm_data(db, org_id, user_id, metric_scope=scope))
    db.add(metric)
    db.flush()
    return metric


@pytest.mark.unit
class TestLoadProjectTraceMetrics:
    @pytest.fixture
    def metrics(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        return {
            "single": _metric(test_db, test_org_id, authenticated_user_id, ["Single-Turn"]),
            "multi": _metric(test_db, test_org_id, authenticated_user_id, ["Multi-Turn"]),
            "both": _metric(
                test_db, test_org_id, authenticated_user_id, ["Single-Turn", "Multi-Turn"]
            ),
            "unassigned": _metric(test_db, test_org_id, authenticated_user_id, ["Single-Turn"]),
        }

    def _load(self, db, org_id, metrics, phase):
        assigned = [str(metrics[k].id) for k in ("single", "multi", "both")]
        loaded = _load_project_trace_metrics(db, org_id, {"metric_ids": assigned}, phase=phase)
        return {m.id for m in loaded}

    def test_nothing_assigned_loads_nothing(self, test_db, test_org_id, metrics):
        assert _load_project_trace_metrics(test_db, test_org_id, {}, phase="turn") == []
        assert (
            _load_project_trace_metrics(test_db, test_org_id, {"metric_ids": []}, phase="turn")
            == []
        )

    def test_turn_phase_loads_single_turn_metrics(self, test_db, test_org_id, metrics):
        """Multi-Turn-only metrics never score a lone turn, conversation or not."""
        ids = self._load(test_db, test_org_id, metrics, "turn")
        assert ids == {metrics["single"].id, metrics["both"].id}

    def test_conversation_phase_loads_multi_turn_metrics(self, test_db, test_org_id, metrics):
        ids = self._load(test_db, test_org_id, metrics, "conversation")
        assert ids == {metrics["multi"].id, metrics["both"].id}

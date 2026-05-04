import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.adaptive_testing import (
    evaluate_tests_for_adaptive_set,
    get_tree_nodes,
    get_tree_tests,
)

_FACTORY_PATCH = "rhesis.sdk.metrics.factory.MetricFactory.create"
_RUN_METRICS_PATCH = "rhesis.backend.app.services.adaptive_testing.evaluation._run_metrics_on_text"


def _create_metric(db, name, organization_id, user_id):
    """Create a Metric row so it can be resolved by name."""
    metric = models.Metric(
        name=name,
        class_name="StubMetric",
        evaluation_prompt="stub prompt",
        score_type="binary",
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(metric)
    db.flush()
    return metric


def _mock_evaluator_result(metric_name, label, score):
    """Build a MetricEvaluator.evaluate()-shaped return dict."""
    is_successful = label == "pass"
    return {metric_name: {"score": score, "is_successful": is_successful}}


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.service
class TestEvaluateTestsForAdaptiveSet:
    """Test evaluate_tests_for_adaptive_set."""

    async def test_evaluate_returns_shape(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        metric = _create_metric(test_db, "TestMetric", test_org_id, authenticated_user_id)
        test_db.commit()

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(return_value=_mock_evaluator_result("TestMetric", "pass", 0.9)),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                overwrite=True,
            )

        assert "evaluated" in result
        assert "results" in result
        assert "failed" in result
        assert result["evaluated"] == 3
        assert len(result["results"]) == 3
        for item in result["results"]:
            assert "test_id" in item
            assert "label" in item
            assert "labeler" in item
            assert "model_score" in item
            assert "metrics" in item
            assert item["metrics"]["TestMetric"]["score"] == 0.9
            assert item["metrics"]["TestMetric"]["is_successful"] is True
            assert item["label"] in ("pass", "fail")
            assert item["labeler"] == metric.name

    async def test_evaluate_persists_metadata(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        metric = _create_metric(
            test_db,
            "PersistMetric",
            test_org_id,
            authenticated_user_id,
        )
        test_db.commit()

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(return_value=_mock_evaluator_result("PersistMetric", "fail", 0.3)),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                overwrite=True,
            )

        for item in result["results"]:
            db_test = test_db.query(models.Test).filter(models.Test.id == item["test_id"]).first()
            meta = db_test.test_metadata or {}
            assert meta["label"] == "fail"
            assert meta["labeler"] == "PersistMetric"
            assert meta["model_score"] == 0.3
            assert meta["metrics"]["PersistMetric"]["score"] == 0.3
            assert meta["metrics"]["PersistMetric"]["is_successful"] is False

    async def test_evaluate_metric_does_not_exist_raises(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        with pytest.raises(ValueError, match="[Mm]etric.*does not exist"):
            await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=["NonExistentMetric"],
            )

    async def test_evaluate_test_set_not_found_raises(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
    ):
        metric = _create_metric(test_db, "AnyMetric", test_org_id, authenticated_user_id)
        test_db.commit()
        with patch(_FACTORY_PATCH, return_value=MagicMock()):
            with pytest.raises(ValueError, match="[Tt]est set not found"):
                await evaluate_tests_for_adaptive_set(
                    db=test_db,
                    test_set_identifier=str(uuid.uuid4()),
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    metric_names=[metric.name],
                )

    async def test_evaluate_filter_by_test_ids(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        metric = _create_metric(test_db, "FilterMetric", test_org_id, authenticated_user_id)
        test_db.commit()

        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        one_id = tests[0].id

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(return_value=_mock_evaluator_result("FilterMetric", "pass", 0.8)),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                test_ids=[uuid.UUID(one_id)],
                overwrite=True,
            )

        assert result["evaluated"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["test_id"] == one_id

    async def test_evaluate_filter_by_topic_include_subtopics(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        metric = _create_metric(test_db, "TopicMetric", test_org_id, authenticated_user_id)
        test_db.commit()

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(return_value=_mock_evaluator_result("TopicMetric", "pass", 0.7)),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                topic="Safety",
                include_subtopics=True,
                overwrite=True,
            )

        assert result["evaluated"] == 3

    async def test_evaluate_filter_by_topic_exclude_subtopics(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        metric = _create_metric(
            test_db,
            "TopicNoSubMetric",
            test_org_id,
            authenticated_user_id,
        )
        test_db.commit()

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(
                    return_value=_mock_evaluator_result("TopicNoSubMetric", "pass", 0.6)
                ),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                topic="Safety",
                include_subtopics=False,
                overwrite=True,
            )

        assert result["evaluated"] == 1

    async def test_evaluate_skips_topic_markers(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        metric = _create_metric(test_db, "SkipMarker", test_org_id, authenticated_user_id)
        test_db.commit()

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(return_value=_mock_evaluator_result("SkipMarker", "pass", 1.0)),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                overwrite=True,
            )

        result_ids = {r["test_id"] for r in result["results"]}
        tree = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        marker_ids = {n.id for n in tree if n.label == "topic_marker"}
        assert result_ids.isdisjoint(marker_ids)

    async def test_evaluate_skips_already_labeled(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """When overwrite=False, tests that already have labels are skipped."""
        metric = _create_metric(test_db, "SkipMetric", test_org_id, authenticated_user_id)
        test_db.commit()

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(return_value=_mock_evaluator_result("SkipMetric", "pass", 1.0)),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                overwrite=False,
            )

        # The fixture has 3 tests, but 2 already have labels ("pass" and "fail")
        assert result["evaluated"] == 1
        assert result["skipped"] == 2

    async def test_evaluate_overwrite_relabels(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """When overwrite=True, tests are evaluated even if they have labels."""
        metric = _create_metric(test_db, "OverwriteMetric", test_org_id, authenticated_user_id)
        test_db.commit()

        with (
            patch(_FACTORY_PATCH, return_value=MagicMock()),
            patch(
                _RUN_METRICS_PATCH,
                new=AsyncMock(
                    return_value=_mock_evaluator_result("OverwriteMetric", "pass", 1.0)
                ),
            ),
        ):
            result = await evaluate_tests_for_adaptive_set(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_names=[metric.name],
                overwrite=True,
            )

        assert result["evaluated"] == 3
        assert result["skipped"] == 0

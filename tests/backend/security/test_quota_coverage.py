"""Quota limits apply on every path that creates the limited thing.

- ENDPOINTS counts every project's endpoints, whatever project the session is on.
- Restoring a project or endpoint from the recycle bin is checked like a create.
- SDK endpoint sync is checked like a create.
- Hosted judge models set on a metric, and the hosted default used for Polyphemus
  users and trace evaluation, are gated on MODEL_TOKENS.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaVerdict
from rhesis.backend.app.services.usage import count_org_endpoints, count_org_projects
from rhesis.backend.metrics.strategies import local
from rhesis.sdk.metrics import MetricConfig
from tests.backend.fixtures.rls import scope_to_project

USER_MODEL_UTILS = "rhesis.backend.app.utils.user_model_utils"


class _FixedPolicyProvider:
    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


@pytest.fixture
def limit():
    saved = QuotaRegistry._provider
    QuotaRegistry.reset()

    def install(resource: QuotaResource, value: int) -> None:
        policy = QuotaPolicy(limits={resource: value}, overage=OveragePolicy.HARD)
        QuotaRegistry.set_quota_provider(_FixedPolicyProvider(policy))

    yield install
    QuotaRegistry._provider = saved


def _exceeded(resource=QuotaResource.MODEL_TOKENS) -> QuotaExceededError:
    return QuotaExceededError(
        QuotaVerdict(
            resource=resource,
            used=10,
            limit=10,
            allowed=False,
            over_limit=True,
            kind="flow",
            period_end=None,
        )
    )


def _project(db: Session, org_id: str, user_id: str) -> models.Project:
    project = models.Project(
        name=f"quota-coverage-{uuid.uuid4().hex[:8]}", organization_id=org_id, user_id=user_id
    )
    db.add(project)
    db.flush()
    return project


def _endpoint(db: Session, org_id: str, user_id: str, project: models.Project) -> models.Endpoint:
    # endpoint has RESTRICTIVE project RLS, so the insert needs the session on its project.
    scope_to_project(db, project.id)
    endpoint = models.Endpoint(
        name=f"quota-coverage-{uuid.uuid4().hex[:8]}",
        url="https://example.com",
        connection_type="REST",
        organization_id=org_id,
        user_id=user_id,
        project_id=project.id,
    )
    db.add(endpoint)
    db.flush()
    return endpoint


@pytest.mark.security
class TestStockCountsSpanProjects:
    def test_endpoint_count_is_the_same_from_every_project(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        project_a = _project(test_db, test_org_id, authenticated_user_id)
        project_b = _project(test_db, test_org_id, authenticated_user_id)
        _endpoint(test_db, test_org_id, authenticated_user_id, project_a)
        _endpoint(test_db, test_org_id, authenticated_user_id, project_b)

        scope_to_project(test_db, project_a.id)
        from_a = count_org_endpoints(test_db, test_org_id)
        scope_to_project(test_db, project_b.id)
        from_b = count_org_endpoints(test_db, test_org_id)

        assert from_a == from_b
        assert from_a >= 2

    def test_project_count_is_the_same_from_every_project(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        project_a = _project(test_db, test_org_id, authenticated_user_id)
        project_b = _project(test_db, test_org_id, authenticated_user_id)

        scope_to_project(test_db, project_a.id)
        from_a = count_org_projects(test_db, test_org_id)
        scope_to_project(test_db, project_b.id)
        assert count_org_projects(test_db, test_org_id) == from_a >= 2


@pytest.mark.security
class TestRestoreIsQuotaChecked:
    def _deleted_project(self, db, org_id, user_id) -> models.Project:
        project = _project(db, org_id, user_id)
        project.deleted_at = datetime.now(timezone.utc)
        db.commit()
        return project

    def test_restoring_a_project_at_the_limit_is_refused(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
        limit,
    ):
        project = self._deleted_project(test_db, test_org_id, authenticated_user_id)
        limit(QuotaResource.PROJECTS, count_org_projects(test_db, test_org_id))

        single = authenticated_client.post(f"/recycle/project/{project.id}/restore")
        bulk = authenticated_client.post("/recycle/bulk-restore/project", json=[str(project.id)])

        assert single.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert single.json()["resource"] == QuotaResource.PROJECTS.value
        assert bulk.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_restoring_a_project_under_the_limit_succeeds(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
        limit,
    ):
        project = self._deleted_project(test_db, test_org_id, authenticated_user_id)
        limit(QuotaResource.PROJECTS, count_org_projects(test_db, test_org_id) + 1)

        response = authenticated_client.post(f"/recycle/project/{project.id}/restore")

        assert response.status_code == status.HTTP_200_OK

    def test_restoring_an_endpoint_at_the_limit_is_refused(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id: str,
        authenticated_user_id: str,
        limit,
    ):
        project = _project(test_db, test_org_id, authenticated_user_id)
        endpoint = _endpoint(test_db, test_org_id, authenticated_user_id, project)
        endpoint.deleted_at = datetime.now(timezone.utc)
        test_db.commit()
        limit(QuotaResource.ENDPOINTS, count_org_endpoints(test_db, test_org_id))

        response = authenticated_client.post(f"/recycle/endpoint/{endpoint.id}/restore")

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert response.json()["resource"] == QuotaResource.ENDPOINTS.value


@pytest.mark.security
class TestBulkRestoreChecksEachItem:
    def test_item_refused_by_the_per_item_check_is_reported_failed(self):
        from rhesis.backend.app.services import recycle as recycle_service

        first, second = uuid.uuid4(), uuid.uuid4()

        def check(item_id):
            if item_id == second:
                raise _exceeded(QuotaResource.PROJECTS)

        with patch.object(recycle_service, "restore_item", return_value=Mock()) as restore:
            results = recycle_service.bulk_restore_with_cascade(
                Mock(), models.Project, [first, second], before_each=check
            )

        assert results["restored"] == [str(first)]
        assert results["failed"][0]["id"] == str(second)
        assert restore.call_count == 1


@pytest.mark.security
class TestAsyncGenerationChecksTheRequestedCount:
    def test_request_larger_than_the_remaining_quota_is_refused(
        self, authenticated_client: TestClient, limit
    ):
        limit(QuotaResource.TEST_GENERATION, 3)
        response = authenticated_client.post(
            "/test_sets/generate",
            json={
                "name": "quota",
                "num_tests": 5,
                "project_id": str(uuid.uuid4()),
                "config": {"requirements": ["be polite"]},
            },
        )
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert response.json()["requested"] == 5


@pytest.mark.security
class TestSdkSyncIsQuotaChecked:
    def _sync(self, db, org_id, user_id, project):
        from rhesis.backend.app.services.endpoint.sdk_sync import sync_sdk_endpoints

        sync = "rhesis.backend.app.services.endpoint.sdk_sync"
        with (
            patch(f"{sync}.generate_and_apply_mappings"),
            patch(f"{sync}.validate_and_update_status"),
        ):
            return asyncio.run(
                sync_sdk_endpoints(
                    db,
                    str(project.id),
                    "development",
                    [{"name": f"fn_{uuid.uuid4().hex[:8]}", "parameters": {}, "metadata": {}}],
                    org_id,
                    user_id,
                )
            )

    def test_new_sdk_endpoint_at_the_limit_is_not_created(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, limit
    ):
        project = _project(test_db, test_org_id, authenticated_user_id)
        scope_to_project(test_db, project.id)
        limit(QuotaResource.ENDPOINTS, count_org_endpoints(test_db, test_org_id))

        stats = self._sync(test_db, test_org_id, authenticated_user_id, project)

        assert stats["created"] == 0
        assert "Quota exceeded for endpoints" in stats["errors"][0]["error"]

    def test_new_sdk_endpoints_past_the_limit_are_all_refused(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, limit
    ):
        from rhesis.backend.app.services.endpoint.sdk_sync import sync_sdk_endpoints

        project = _project(test_db, test_org_id, authenticated_user_id)
        scope_to_project(test_db, project.id)
        limit(QuotaResource.ENDPOINTS, count_org_endpoints(test_db, test_org_id) + 1)
        functions = [
            {"name": f"fn_{uuid.uuid4().hex[:8]}", "parameters": {}, "metadata": {}}
            for _ in range(2)
        ]
        sync = "rhesis.backend.app.services.endpoint.sdk_sync"
        with (
            patch(f"{sync}.generate_and_apply_mappings") as mapping,
            patch(f"{sync}.validate_and_update_status"),
        ):
            stats = asyncio.run(
                sync_sdk_endpoints(
                    test_db,
                    str(project.id),
                    "development",
                    functions,
                    test_org_id,
                    authenticated_user_id,
                )
            )

        assert stats["created"] == 0
        assert len(stats["errors"]) == 2
        mapping.assert_not_called()

    def test_new_sdk_endpoint_under_the_limit_is_created(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, limit
    ):
        project = _project(test_db, test_org_id, authenticated_user_id)
        scope_to_project(test_db, project.id)
        limit(QuotaResource.ENDPOINTS, count_org_endpoints(test_db, test_org_id) + 1)

        stats = self._sync(test_db, test_org_id, authenticated_user_id, project)

        assert stats["created"] == 1


def _model_row(provider: str, key):
    row = Mock()
    row.provider_type.type_value = provider
    row.key = key
    row.endpoint = None
    row.model_name = "default"
    row.name = "judge"
    return row


@pytest.mark.security
class TestMetricJudgeModelIsGated:
    def _resolve(self, row):
        with patch("rhesis.backend.app.crud.model.get_model", return_value=row):
            return local._resolve_metric_model(str(uuid.uuid4()), Mock(), "org", "metric")

    def test_hosted_judge_at_the_token_limit_raises(self):
        with patch(f"{USER_MODEL_UTILS}._enforce_model_token_quota", side_effect=_exceeded()):
            with pytest.raises(QuotaExceededError):
                self._resolve(_model_row("rhesis", None))

    def test_judge_on_the_orgs_own_key_is_not_gated(self):
        with (
            patch(f"{USER_MODEL_UTILS}._enforce_model_token_quota") as gate,
            patch("rhesis.sdk.models.factory.get_model", return_value=Mock()),
        ):
            assert self._resolve(_model_row("openai", "sk-org")) is not None
        gate.assert_not_called()

    def test_pre_resolved_quota_error_refuses_only_its_metrics(self):
        from rhesis.backend.jobs.execution.batch.context import _resolve_metric_judge_models

        blocked_id = str(uuid.uuid4())
        config = MetricConfig(
            class_name="NumericJudge",
            backend="rhesis",
            name="judged",
            parameters={"model_id": blocked_id},
        )
        with patch.object(local, "_resolve_metric_model", side_effect=_exceeded()):
            resolved = _resolve_metric_judge_models(Mock(), "org", [config], {})
        assert isinstance(resolved[blocked_id], QuotaExceededError)

        other = MetricConfig(class_name="NumericJudge", backend="rhesis", name="default judged")
        refused: list = []
        with patch.object(local, "create_metric", return_value=Mock()):
            tasks = local.prepare_metrics(
                [config, other],
                model=Mock(),
                organization_id="org",
                metric_models=resolved,
                refused=refused,
            )
        assert [task[2].name for task in tasks] == ["default judged"]
        assert [r["name"] for r in refused] == ["judged"]
        assert refused[0]["error_type"] == "QuotaExceeded"

    def test_quota_blocked_metric_is_refused_not_rescored_on_the_default(self):
        config = MetricConfig(
            class_name="NumericJudge",
            backend="rhesis",
            name="judged",
            parameters={"model_id": str(uuid.uuid4())},
        )
        refused: list = []
        with patch.object(local, "_select_metric_model", side_effect=_exceeded()):
            tasks = local.prepare_metrics(
                [config], model=Mock(), db=Mock(), organization_id="org", refused=refused
            )

        assert tasks == []
        assert refused[0]["error_type"] == "QuotaExceeded"


@pytest.mark.security
class TestHostedDefaultsAreGated:
    def test_polyphemus_users_fast_default_is_gated(self):
        from rhesis.backend.app.services.test_generation_pipeline import _resolve_config_llm

        user = Mock()
        user.settings.models.generation.model_id = uuid.uuid4()
        with (
            patch(
                "rhesis.backend.app.crud.model.get_model",
                return_value=_model_row("polyphemus", None),
            ),
            patch(f"{USER_MODEL_UTILS}._enforce_model_token_quota", side_effect=_exceeded()),
            pytest.raises(QuotaExceededError),
        ):
            _resolve_config_llm(Mock(), user)

    def test_polyphemus_users_test_config_default_is_gated(self):
        from rhesis.backend.app.services.test_config_generator import TestConfigGeneratorService

        user = Mock()
        user.settings.models.generation.model_id = uuid.uuid4()
        with (
            patch(
                "rhesis.backend.app.crud.model.get_model",
                return_value=_model_row("polyphemus", None),
            ),
            patch(f"{USER_MODEL_UTILS}._enforce_model_token_quota", side_effect=_exceeded()),
            pytest.raises(QuotaExceededError),
        ):
            TestConfigGeneratorService(Mock(), user)

    def test_background_resolution_at_the_limit_raises(
        self, test_db: Session, authenticated_user_id: str
    ):
        from rhesis.backend.app.utils.user_model_utils import resolve_model

        with (
            patch(f"{USER_MODEL_UTILS}._enforce_model_token_quota", side_effect=_exceeded()),
            pytest.raises(QuotaExceededError),
        ):
            resolve_model(test_db, str(authenticated_user_id), "evaluation")

    def test_generate_test_config_returns_402_at_the_limit(self, authenticated_client: TestClient):
        with patch(
            "rhesis.backend.app.routers.services.TestConfigGeneratorService",
            side_effect=_exceeded(),
        ):
            response = authenticated_client.post(
                "/services/generate/test_config", json={"prompt": "a chatbot"}
            )
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def _prepare(self, project):
        from rhesis.backend.jobs.telemetry import evaluate

        return evaluate._build_evaluator(Mock(), project, "trace", "org")

    def test_trace_evaluation_setup_raises_at_the_limit(self):
        # The task catches it and marks the trace Skipped (jobs/test_trace_eval_token_limit.py).
        with (
            patch(f"{USER_MODEL_UTILS}.resolve_model", side_effect=_exceeded()),
            pytest.raises(QuotaExceededError),
        ):
            self._prepare(Mock())

    def test_trace_evaluation_without_a_user_uses_the_gated_default(self):
        project = Mock(owner=None, user=None)
        with (
            patch(f"{USER_MODEL_UTILS}.resolve_default_hosted_model", return_value=Mock()) as gated,
            patch("rhesis.backend.metrics.evaluator.MetricEvaluator") as evaluator,
        ):
            assert self._prepare(project) is not None
        gated.assert_called_once()
        assert evaluator.call_args.kwargs["require_model"] is True

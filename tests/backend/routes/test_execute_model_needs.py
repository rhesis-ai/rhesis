"""The execute and re-score routes check only the models the run uses (issue #2853).

The check used to be a route dependency, so it ran before the request was read and
asked for the evaluation and execution models whatever the run contained. It now runs
once the run's metrics are resolved.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app import models
from rhesis.backend.app.constants import TestType
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
from rhesis.backend.app.utils.model_errors import MODEL_NOT_CONFIGURED, ModelConfigurationError

_RESOLVE = "rhesis.backend.app.utils.user_model_utils.resolve_model"
_OWN_MODEL_BROKEN = ModelConfigurationError("API key not found for provider 'openai'")


def _test_set_with_metric(test_db, organization, user, db_status, backend, multi_turn=False):
    """A test set holding one test, scored by one metric of *backend*."""
    org_id, user_id = organization.id, user.id
    test_type = get_or_create_type_lookup(
        test_db,
        "TestType",
        (TestType.MULTI_TURN if multi_turn else TestType.SINGLE_TURN).value,
        str(org_id),
        str(user_id),
    )
    backend_type = get_or_create_type_lookup(
        test_db, "BackendType", backend, str(org_id), str(user_id)
    )
    metric_type = get_or_create_type_lookup(
        test_db, "MetricType", "custom-prompt", str(org_id), str(user_id)
    )
    metric = models.Metric(
        metric_scope=["Single-Turn"],
        name=f"{backend} metric",
        class_name="NumericJudge",
        score_type="numeric",
        evaluation_prompt="Evaluate",
        backend_type_id=backend_type.id,
        metric_type_id=metric_type.id,
        organization_id=org_id,
        user_id=user_id,
    )
    test_set = models.TestSet(
        name=f"{backend}-metric-test-set",
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
    )
    test = models.Test(
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
        test_type_id=test_type.id,
        test_configuration={"goal": "Book a flight"} if multi_turn else None,
    )
    test_db.add_all([metric, test_set, test])
    test_db.flush()
    test_db.execute(
        models.test_set_metric_association.insert().values(
            test_set_id=test_set.id, metric_id=metric.id, organization_id=org_id, user_id=user_id
        )
    )
    test_db.execute(
        models.test_test_set_association.insert().values(
            test_id=test.id, test_set_id=test_set.id, organization_id=org_id, user_id=user_id
        )
    )
    return test_set


@pytest.fixture
def sdk_only_configuration(test_db, test_organization, db_user, db_status, db_test_configuration):
    test_set = _test_set_with_metric(test_db, test_organization, db_user, db_status, "sdk")
    db_test_configuration.test_set_id = test_set.id
    test_db.commit()
    return db_test_configuration


@pytest.fixture
def llm_metric_configuration(test_db, test_organization, db_user, db_status, db_test_configuration):
    test_set = _test_set_with_metric(test_db, test_organization, db_user, db_status, "rhesis")
    db_test_configuration.test_set_id = test_set.id
    test_db.commit()
    return db_test_configuration


@pytest.fixture
def multi_turn_sdk_configuration(
    test_db, test_organization, db_user, db_status, db_test_configuration
):
    test_set = _test_set_with_metric(
        test_db, test_organization, db_user, db_status, "sdk", multi_turn=True
    )
    db_test_configuration.test_set_id = test_set.id
    test_db.commit()
    return db_test_configuration


def _configuration_count(test_db, test_set_id):
    return (
        test_db.query(models.TestConfiguration)
        .filter(models.TestConfiguration.test_set_id == test_set_id)
        .count()
    )


def _run_count(test_db, configuration):
    return (
        test_db.query(models.TestRun)
        .filter(models.TestRun.test_configuration_id == configuration.id)
        .count()
    )


class TestExecuteTestConfiguration:
    def test_sdk_only_run_starts_without_an_evaluation_model(
        self, authenticated_client: TestClient, test_db, sdk_only_configuration
    ):
        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN) as resolve,
            patch(
                "rhesis.backend.app.routers.test_configuration.launch_job",
                return_value=MagicMock(id="task-1"),
            ) as launch,
        ):
            response = authenticated_client.post(
                f"/test_configurations/{sdk_only_configuration.id}/execute"
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["status"] == "submitted"
        resolve.assert_not_called()
        launch.assert_called_once()

        run = test_db.get(models.TestRun, response.json()["test_run_id"])
        assert run.attributes["metric_plan"]["metric_backends"] == ["sdk"]
        assert run.attributes["metric_plan"]["has_multi_turn"] is False

    def test_llm_metric_is_refused_when_the_orgs_evaluation_model_is_broken(
        self, authenticated_client: TestClient, test_db, llm_metric_configuration
    ):
        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN),
            patch("rhesis.backend.app.routers.test_configuration.launch_job") as launch,
        ):
            response = authenticated_client.post(
                f"/test_configurations/{llm_metric_configuration.id}/execute"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == MODEL_NOT_CONFIGURED
        assert "api key" in detail["message"].lower()
        assert "deployment_hint" not in detail
        launch.assert_not_called()
        assert _run_count(test_db, llm_metric_configuration) == 0

    def test_llm_metric_is_refused_when_the_deployment_default_cannot_be_built(
        self, authenticated_client: TestClient, test_db, llm_metric_configuration
    ):
        """The #2681 split: the deployment's own default is a 500, with a hint."""
        with (
            patch(_RESOLVE, side_effect=ValueError("RHESIS_API_KEY is not set")),
            patch("rhesis.backend.app.routers.test_configuration.launch_job") as launch,
        ):
            response = authenticated_client.post(
                f"/test_configurations/{llm_metric_configuration.id}/execute"
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == MODEL_NOT_CONFIGURED
        assert "DEFAULT_EVALUATION_MODEL" in detail["deployment_hint"]
        assert "RHESIS_API_KEY" not in response.text
        launch.assert_not_called()

    def test_llm_metric_only_asks_for_the_evaluation_model(
        self, authenticated_client: TestClient, llm_metric_configuration
    ):
        """No multi-turn test, so a broken execution model is not this run's problem."""
        with (
            patch(_RESOLVE, return_value=MagicMock()) as resolve,
            patch(
                "rhesis.backend.app.routers.test_configuration.launch_job",
                return_value=MagicMock(id="task-1"),
            ),
        ):
            response = authenticated_client.post(
                f"/test_configurations/{llm_metric_configuration.id}/execute"
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]

    def test_multi_turn_run_still_asks_for_both_models(
        self, authenticated_client: TestClient, multi_turn_sdk_configuration
    ):
        """Even with SDK metrics only: Penelope runs the conversation and the goal is judged."""
        with (
            patch(_RESOLVE, return_value=MagicMock()) as resolve,
            patch(
                "rhesis.backend.app.routers.test_configuration.launch_job",
                return_value=MagicMock(id="task-1"),
            ),
        ):
            response = authenticated_client.post(
                f"/test_configurations/{multi_turn_sdk_configuration.id}/execute"
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation", "execution"]

    def test_multi_turn_run_is_refused_when_the_execution_model_is_broken(
        self, authenticated_client: TestClient, multi_turn_sdk_configuration
    ):
        def _resolve(_db, _user, purpose, override=None):
            if purpose == "execution":
                raise ValueError("RHESIS_API_KEY is not set")
            return MagicMock()

        with (
            patch(_RESOLVE, side_effect=_resolve),
            patch("rhesis.backend.app.routers.test_configuration.launch_job") as launch,
        ):
            response = authenticated_client.post(
                f"/test_configurations/{multi_turn_sdk_configuration.id}/execute"
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
        assert "DEFAULT_EXECUTION_MODEL" in response.json()["detail"]["deployment_hint"]
        launch.assert_not_called()


class TestExecuteTestSet:
    def test_sdk_only_run_starts_without_an_evaluation_model(
        self, authenticated_client: TestClient, sdk_only_configuration
    ):
        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN) as resolve,
            patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task-1")),
        ):
            response = authenticated_client.post(
                f"/test_sets/{sdk_only_configuration.test_set_id}"
                f"/execute/{sdk_only_configuration.endpoint_id}"
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["status"] == "submitted"
        resolve.assert_not_called()

    def test_llm_metric_is_refused_when_the_evaluation_model_is_broken(
        self, authenticated_client: TestClient, llm_metric_configuration
    ):
        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN),
            patch("rhesis.backend.jobs.launch_job") as launch,
        ):
            response = authenticated_client.post(
                f"/test_sets/{llm_metric_configuration.test_set_id}"
                f"/execute/{llm_metric_configuration.endpoint_id}"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert response.json()["detail"]["error_code"] == MODEL_NOT_CONFIGURED
        launch.assert_not_called()


class TestRescore:
    """Re-score had no model check at all."""

    def test_llm_metric_is_refused_when_the_evaluation_model_is_broken(
        self, authenticated_client: TestClient, llm_metric_configuration, db_test_run
    ):
        assert db_test_run.test_configuration_id == llm_metric_configuration.id

        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN),
            patch("rhesis.backend.jobs.launch_job") as launch,
        ):
            response = authenticated_client.post(f"/test_runs/{db_test_run.id}/rescore")

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == MODEL_NOT_CONFIGURED
        assert "re-score this test run" in detail["message"]
        launch.assert_not_called()

    def test_deployment_default_that_cannot_be_built_is_a_500(
        self, authenticated_client: TestClient, llm_metric_configuration, db_test_run
    ):
        with (
            patch(_RESOLVE, side_effect=ValueError("RHESIS_API_KEY is not set")),
            patch("rhesis.backend.jobs.launch_job") as launch,
        ):
            response = authenticated_client.post(f"/test_runs/{db_test_run.id}/rescore")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
        assert response.json()["detail"]["error_code"] == MODEL_NOT_CONFIGURED
        launch.assert_not_called()

    def test_checks_the_evaluation_model_the_rescore_names(
        self, authenticated_client: TestClient, llm_metric_configuration, db_test_run
    ):
        model_id = str(uuid.uuid4())
        with (
            patch(_RESOLVE, return_value=MagicMock()) as resolve,
            patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task-1")),
        ):
            response = authenticated_client.post(
                f"/test_runs/{db_test_run.id}/rescore", json={"evaluation_model_id": model_id}
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert [(c.args[2], c.kwargs["override"]) for c in resolve.call_args_list] == [
            ("evaluation", model_id)
        ]

    def test_multi_turn_rescore_asks_for_the_evaluation_model_only(
        self, authenticated_client: TestClient, multi_turn_sdk_configuration, db_test_run
    ):
        """A re-score replays the stored conversation, so Penelope never starts."""
        with (
            patch(_RESOLVE, return_value=MagicMock()) as resolve,
            patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task-1")),
        ):
            response = authenticated_client.post(f"/test_runs/{db_test_run.id}/rescore")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]

    def test_sdk_only_rescore_starts_without_an_evaluation_model(
        self, authenticated_client: TestClient, sdk_only_configuration, db_test_run
    ):
        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN) as resolve,
            patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task-1")),
        ):
            response = authenticated_client.post(f"/test_runs/{db_test_run.id}/rescore")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["status"] == "submitted"
        resolve.assert_not_called()


def _single_turn_test(test_db, organization, user, db_status, backend):
    """A single-turn test whose requirement carries one metric of *backend*."""
    org_id, user_id = organization.id, user.id
    backend_type = get_or_create_type_lookup(
        test_db, "BackendType", backend, str(org_id), str(user_id)
    )
    metric_type = get_or_create_type_lookup(
        test_db, "MetricType", "custom-prompt", str(org_id), str(user_id)
    )
    test_type = get_or_create_type_lookup(
        test_db, "TestType", TestType.SINGLE_TURN.value, str(org_id), str(user_id)
    )
    metric = models.Metric(
        metric_scope=["Single-Turn"],
        name=f"{backend} requirement metric",
        class_name="NumericJudge",
        score_type="numeric",
        evaluation_prompt="Evaluate",
        backend_type_id=backend_type.id,
        metric_type_id=metric_type.id,
        organization_id=org_id,
        user_id=user_id,
    )
    requirement = models.Requirement(
        name=f"{backend} requirement", organization_id=org_id, user_id=user_id
    )
    prompt = models.Prompt(
        content="What is 2+2?",
        expected_response="4",
        language_code="en",
        organization_id=org_id,
        user_id=user_id,
        status_id=db_status.id,
    )
    test_db.add_all([metric, requirement, prompt])
    test_db.flush()
    test_db.execute(
        models.requirement_metric_association.insert().values(
            requirement_id=requirement.id,
            metric_id=metric.id,
            organization_id=org_id,
            user_id=user_id,
        )
    )
    test = models.Test(
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
        test_type_id=test_type.id,
        prompt_id=prompt.id,
        requirement_id=requirement.id,
    )
    test_db.add(test)
    test_db.commit()
    return test


class TestExecuteSingleTest:
    """``POST /tests/execute`` runs one test in place, under the same rule."""

    def _execute(self, client, test, endpoint, evaluate_metrics=True):
        with patch("rhesis.backend.app.services.test_execution.SingleTurnRunner") as runner_class:
            runner_class.return_value.run = AsyncMock(return_value=(1.0, {"output": "4"}, {}))
            response = client.post(
                "/tests/execute",
                json={
                    "test_id": str(test.id),
                    "endpoint_id": str(endpoint.id),
                    "evaluate_metrics": evaluate_metrics,
                },
            )
        return response, runner_class.return_value.run

    def test_sdk_only_test_runs_without_an_evaluation_model(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_status,
        db_endpoint,
    ):
        test = _single_turn_test(test_db, test_organization, db_user, db_status, "sdk")

        with patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN) as resolve:
            response, run = self._execute(authenticated_client, test, db_endpoint)

        assert response.status_code == status.HTTP_200_OK, response.text
        resolve.assert_not_called()
        assert run.call_args.kwargs["model"] is None

    def test_llm_metric_is_refused_when_the_evaluation_model_is_broken(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_status,
        db_endpoint,
    ):
        test = _single_turn_test(test_db, test_organization, db_user, db_status, "rhesis")

        with patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN):
            response, run = self._execute(authenticated_client, test, db_endpoint)

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert response.json()["detail"]["error_code"] == MODEL_NOT_CONFIGURED
        run.assert_not_called()

    def test_without_metric_evaluation_no_model_is_needed(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_status,
        db_endpoint,
    ):
        """``evaluate_metrics=false`` judges nothing, whatever metrics the test has."""
        test = _single_turn_test(test_db, test_organization, db_user, db_status, "rhesis")

        with patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN) as resolve:
            response, run = self._execute(
                authenticated_client, test, db_endpoint, evaluate_metrics=False
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        resolve.assert_not_called()
        assert run.call_args.kwargs["evaluate_metrics"] is False


class TestExecuteSingleMultiTurnTest:
    """A multi-turn test run in place needs both models, whatever its metrics are."""

    @pytest.fixture
    def multi_turn_test(self, test_db, test_organization, db_user, db_status):
        test_type = get_or_create_type_lookup(
            test_db,
            "TestType",
            TestType.MULTI_TURN.value,
            str(test_organization.id),
            str(db_user.id),
        )
        test = models.Test(
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            test_type_id=test_type.id,
            test_configuration={"goal": "Book a flight"},
        )
        test_db.add(test)
        test_db.commit()
        return test

    def _execute(self, client, test, endpoint):
        with patch("rhesis.backend.app.services.test_execution.MultiTurnRunner") as runner_class:
            runner_class.return_value.run = AsyncMock(return_value=(1.0, {"turns": 1}, {}))
            response = client.post(
                "/tests/execute",
                json={"test_id": str(test.id), "endpoint_id": str(endpoint.id)},
            )
        return response, runner_class.return_value.run

    def test_builds_both_models(
        self, authenticated_client: TestClient, multi_turn_test, db_endpoint
    ):
        with patch(_RESOLVE, side_effect=lambda _db, _user, purpose, override=None: purpose):
            response, run = self._execute(authenticated_client, multi_turn_test, db_endpoint)

        assert response.status_code == status.HTTP_200_OK, response.text
        assert run.call_args.kwargs["evaluation_model"] == "evaluation"
        assert run.call_args.kwargs["execution_model"] == "execution"

    def test_is_refused_when_the_execution_model_cannot_be_built(
        self, authenticated_client: TestClient, multi_turn_test, db_endpoint
    ):
        def _resolve(_db, _user, purpose, override=None):
            if purpose == "execution":
                raise ValueError("RHESIS_API_KEY is not set")
            return MagicMock()

        with patch(_RESOLVE, side_effect=_resolve):
            response, run = self._execute(authenticated_client, multi_turn_test, db_endpoint)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == MODEL_NOT_CONFIGURED
        assert "DEFAULT_EXECUTION_MODEL" in detail["deployment_hint"]
        run.assert_not_called()


class TestRefusedRunLeavesNoConfiguration:
    """Execute and re-score create a test configuration before the models can be checked."""

    def test_refused_execute(
        self, authenticated_client: TestClient, test_db, llm_metric_configuration
    ):
        test_set_id = llm_metric_configuration.test_set_id
        before = _configuration_count(test_db, test_set_id)

        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN),
            patch("rhesis.backend.jobs.launch_job"),
        ):
            response = authenticated_client.post(
                f"/test_sets/{test_set_id}/execute/{llm_metric_configuration.endpoint_id}"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert _configuration_count(test_db, test_set_id) == before

    def test_refused_rescore(
        self, authenticated_client: TestClient, test_db, llm_metric_configuration, db_test_run
    ):
        test_set_id = llm_metric_configuration.test_set_id
        before = _configuration_count(test_db, test_set_id)

        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN),
            patch("rhesis.backend.jobs.launch_job"),
        ):
            response = authenticated_client.post(f"/test_runs/{db_test_run.id}/rescore")

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert _configuration_count(test_db, test_set_id) == before

    def test_accepted_execute_and_rescore_each_keep_theirs(
        self, authenticated_client: TestClient, test_db, sdk_only_configuration, db_test_run
    ):
        """The counterpart, so the two tests above cannot pass by counting nothing."""
        test_set_id = sdk_only_configuration.test_set_id
        before = _configuration_count(test_db, test_set_id)

        with patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task-1")):
            executed = authenticated_client.post(
                f"/test_sets/{test_set_id}/execute/{sdk_only_configuration.endpoint_id}"
            )
            rescored = authenticated_client.post(f"/test_runs/{db_test_run.id}/rescore")

        assert executed.status_code == status.HTTP_200_OK, executed.text
        assert rescored.status_code == status.HTTP_200_OK, rescored.text
        assert _configuration_count(test_db, test_set_id) == before + 2

    def test_a_failure_while_creating_the_configuration_closes_the_savepoint(self, test_db):
        """So a caller that carries on is not left inside it."""
        from rhesis.backend.app.services import test_set as test_set_service

        db = MagicMock()
        with (
            patch("rhesis.backend.app.crud.test_set.resolve_test_set"),
            patch("rhesis.backend.app.crud.endpoint.get_endpoint"),
            patch.object(test_set_service, "_validate_user_access"),
            patch.object(test_set_service, "_validate_test_set_not_empty"),
            patch.object(test_set_service, "enforce_test_run_quota"),
            patch.object(
                test_set_service, "_create_test_configuration", side_effect=RuntimeError("boom")
            ),
        ):
            with pytest.raises(RuntimeError):
                test_set_service.execute_test_set_on_endpoint(
                    db=db,
                    test_set_identifier="set-1",
                    endpoint_id="endpoint-1",
                    current_user=MagicMock(),
                    metrics=[{"id": "m1", "name": "m"}],
                )

        db.begin_nested.return_value.rollback.assert_called_once()

    def test_refused_execute_when_the_caller_carries_on(
        self, test_db, db_user, llm_metric_configuration
    ):
        """Onboarding catches the refusal and commits later, so a rollback of the
        whole request cannot be what removes the configuration."""
        from rhesis.backend.app.services.test_set import execute_test_set_on_endpoint
        from rhesis.backend.app.utils.model_errors import ModelNotConfiguredError

        test_set_id = llm_metric_configuration.test_set_id
        before = _configuration_count(test_db, test_set_id)

        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN),
            patch("rhesis.backend.jobs.launch_job"),
        ):
            with pytest.raises(ModelNotConfiguredError):
                execute_test_set_on_endpoint(
                    db=test_db,
                    test_set_identifier=str(test_set_id),
                    endpoint_id=llm_metric_configuration.endpoint_id,
                    current_user=db_user,
                    organization_id=str(db_user.organization_id),
                    user_id=str(db_user.id),
                )
        test_db.commit()

        assert _configuration_count(test_db, test_set_id) == before

    def test_refused_rescore_when_the_caller_carries_on(
        self, test_db, db_user, llm_metric_configuration, db_test_run
    ):
        from rhesis.backend.app.services.test_run import rescore_test_run
        from rhesis.backend.app.utils.model_errors import ModelNotConfiguredError

        test_set_id = llm_metric_configuration.test_set_id
        before = _configuration_count(test_db, test_set_id)

        with (
            patch(_RESOLVE, side_effect=_OWN_MODEL_BROKEN),
            patch("rhesis.backend.jobs.launch_job"),
        ):
            with pytest.raises(ModelNotConfiguredError):
                rescore_test_run(
                    db=test_db, reference_test_run_id=str(db_test_run.id), current_user=db_user
                )
        test_db.commit()

        assert _configuration_count(test_db, test_set_id) == before

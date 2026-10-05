"""Which models a run needs, and building only those (issue #2853).

A test set whose metrics are all SDK metrics never calls a judge, so it must not be
refused, or fail in the worker, for lack of an evaluation model.
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaVerdict
from rhesis.backend.app.services.run_models import (
    RunModelNeeds,
    build_models,
    check_run_models,
    metric_backends,
    model_needs,
    model_needs_from_plan,
    resolve_run_models,
)
from rhesis.backend.app.utils.model_errors import ModelConfigurationError, ModelNotConfiguredError
from rhesis.backend.app.utils.user_model_utils import (
    build_model_or_raise,
    model_setup_problem,
)

_RESOLVE = "rhesis.backend.app.utils.user_model_utils.resolve_model"
_DEFAULT = "rhesis.backend.app.utils.user_model_utils.resolve_default_hosted_model"
_GET_USER = "rhesis.backend.app.services.run_models.get_user_by_id"
_RECORD = "rhesis.backend.app.services.run_models.record_resolved_evaluation_model"


def _plan(backends, has_multi_turn=False):
    return {"metric_backends": backends, "has_multi_turn": has_multi_turn}


def _quota_error():
    return QuotaExceededError(
        QuotaVerdict(
            resource=QuotaResource.MODEL_TOKENS,
            used=2,
            limit=1,
            allowed=False,
            over_limit=True,
            kind="flow",
            period_end="2026-10-01",
        )
    )


def _config(attributes=None, user_id="user-1"):
    config = MagicMock()
    config.attributes = attributes or {}
    config.organization_id = "org-1"
    config.user_id = user_id
    return config


def _run(plan):
    run = MagicMock()
    run.attributes = {"metric_plan": plan} if plan is not None else {}
    return run


@pytest.mark.unit
class TestModelNeeds:
    @pytest.mark.parametrize(
        "backends, has_multi_turn, replay, evaluation, execution",
        [
            # SDK metrics only: no judge, no Penelope.
            (["sdk"], False, False, False, False),
            # One LLM-backed metric.
            (["rhesis"], False, False, True, False),
            (["deepeval"], False, False, True, False),
            # Mixed.
            (["rhesis", "sdk"], False, False, True, False),
            # Multi-turn needs both, whatever the metrics are.
            (["sdk"], True, False, True, True),
            ([], True, False, True, True),
            (["rhesis"], True, False, True, True),
            # No metrics at all.
            ([], False, False, False, False),
            # A metric row with no backend recorded is not known to be an SDK metric.
            ([None], False, False, True, False),
            # A replay starts no conversation, so it has no use for the execution model.
            ([], True, True, True, False),
            (["sdk"], False, True, False, False),
        ],
    )
    def test_truth_table(self, backends, has_multi_turn, replay, evaluation, execution):
        assert model_needs(backends, has_multi_turn, replay) == RunModelNeeds(
            evaluation=evaluation, execution=execution
        )

    def test_reads_the_plan(self):
        assert model_needs_from_plan(_plan(["sdk"])) == RunModelNeeds(False, False)
        assert model_needs_from_plan(_plan(["rhesis", "sdk"])) == RunModelNeeds(True, False)
        assert model_needs_from_plan(_plan(["sdk"], has_multi_turn=True)) == RunModelNeeds(
            True, True
        )

    @pytest.mark.parametrize("plan", [None, {}, {"requirements": [], "test_order": []}])
    def test_no_usable_plan_builds_both(self, plan):
        """A plan that failed to build, or one saved before it recorded backends."""
        assert model_needs_from_plan(plan) == RunModelNeeds(True, True)
        assert model_needs_from_plan(plan, replay=True) == RunModelNeeds(True, False)

    def test_metric_backends_are_read_by_type_id(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [("sdk",)]
        sdk_metric = MagicMock(backend_type_id="type-1")

        assert metric_backends(db, [sdk_metric, sdk_metric]) == ["sdk"]
        assert metric_backends(db, []) == []

    def test_a_metric_with_no_backend_counts_as_rhesis(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [("sdk",)]
        metrics = [MagicMock(backend_type_id="type-1"), MagicMock(backend_type_id=None)]

        assert metric_backends(db, metrics) == ["rhesis", "sdk"]

    def test_a_backend_that_cannot_be_read_is_not_taken_for_sdk(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [("sdk",)]
        metrics = [MagicMock(backend_type_id="type-1"), MagicMock(backend_type_id="type-2")]

        assert metric_backends(db, metrics) == ["rhesis", "sdk"]


@pytest.mark.unit
class TestBuildModels:
    def test_builds_nothing_when_nothing_is_needed(self):
        with patch(_RESOLVE) as resolve:
            models = build_models(MagicMock(), MagicMock(), RunModelNeeds(False, False))

        resolve.assert_not_called()
        assert models.evaluation is None and models.execution is None

    def test_builds_only_the_evaluation_model(self):
        db, user = MagicMock(), MagicMock()
        with patch(_RESOLVE, return_value="judge") as resolve:
            models = build_models(
                db, user, RunModelNeeds(True, False), evaluation_model_id="model-1"
            )

        resolve.assert_called_once_with(db, user, "evaluation", override="model-1")
        assert models.evaluation == "judge" and models.execution is None

    def test_builds_both_with_their_overrides(self):
        db, user = MagicMock(), MagicMock()
        with patch(_RESOLVE, side_effect=lambda _db, _user, purpose, override: purpose) as resolve:
            models = build_models(
                db,
                user,
                RunModelNeeds(True, True),
                evaluation_model_id="eval-id",
                execution_model_id="exec-id",
            )

        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation", "execution"]
        assert [c.kwargs["override"] for c in resolve.call_args_list] == ["eval-id", "exec-id"]
        assert (models.evaluation, models.execution) == ("evaluation", "execution")

    def test_the_orgs_own_broken_model_is_reported_as_theirs(self):
        cause = ModelConfigurationError("API key not found for provider 'openai'")
        with patch(_RESOLVE, side_effect=cause):
            with pytest.raises(ModelNotConfiguredError) as exc_info:
                build_models(MagicMock(), MagicMock(), RunModelNeeds(True, False))

        assert exc_info.value.own_model is True
        assert exc_info.value.purpose == "evaluation"
        assert exc_info.value.deployment_hint is None

    @pytest.mark.parametrize(
        "cause", [ValueError("RHESIS_API_KEY is not set"), ImportError("No module named torch")]
    )
    def test_an_unbuildable_deployment_default_is_reported_as_the_deployments(self, cause):
        with patch(_RESOLVE, side_effect=cause):
            with pytest.raises(ModelNotConfiguredError) as exc_info:
                build_models(MagicMock(), MagicMock(), RunModelNeeds(True, False))

        assert exc_info.value.own_model is False
        assert "DEFAULT_EVALUATION_MODEL" in exc_info.value.deployment_hint

    def test_names_the_purpose_that_failed(self):
        def _resolve(_db, _user, purpose, override=None):
            if purpose == "execution":
                raise ValueError("RHESIS_API_KEY is not set")
            return "judge"

        with patch(_RESOLVE, side_effect=_resolve):
            with pytest.raises(ModelNotConfiguredError) as exc_info:
                build_models(MagicMock(), MagicMock(), RunModelNeeds(True, True))

        assert exc_info.value.purpose == "execution"
        assert "DEFAULT_EXECUTION_MODEL" in exc_info.value.deployment_hint

    def test_quota_error_is_not_swallowed(self):
        """QuotaExceededError has to reach its own handler to become a 402."""
        with patch(_RESOLVE, side_effect=_quota_error()):
            with pytest.raises(QuotaExceededError):
                build_models(MagicMock(), MagicMock(), RunModelNeeds(True, False))


@pytest.mark.unit
class TestOneClassifier:
    """``build_model_or_raise`` is the one place that decides a model cannot be built."""

    def test_returns_the_model(self):
        db, user = MagicMock(), MagicMock()
        with patch(_RESOLVE, return_value="judge") as resolve:
            assert build_model_or_raise(db, user, "evaluation", "model-1") == "judge"

        resolve.assert_called_once_with(db, user, "evaluation", override="model-1")

    def test_quota_passes_through_but_counts_as_usable_for_readiness(self):
        with patch(_RESOLVE, side_effect=_quota_error()):
            with pytest.raises(QuotaExceededError):
                build_model_or_raise(MagicMock(), MagicMock(), "evaluation")
            assert model_setup_problem(MagicMock(), MagicMock(), "evaluation") is None

    def test_readiness_reports_the_same_problem(self):
        with patch(_RESOLVE, side_effect=ValueError("RHESIS_API_KEY is not set")):
            with pytest.raises(ModelNotConfiguredError) as exc_info:
                build_model_or_raise(MagicMock(), MagicMock(), "evaluation")
            problem = model_setup_problem(MagicMock(), MagicMock(), "evaluation")

        assert problem.detail() == exc_info.value.detail()
        assert problem.own_model is False


@pytest.mark.unit
class TestCheckRunModels:
    def test_an_sdk_only_run_is_not_checked_against_any_model(self):
        with patch(_RESOLVE) as resolve:
            check_run_models(MagicMock(), MagicMock(), _config(), _plan(["sdk"]))

        resolve.assert_not_called()

    def test_an_llm_metric_is_refused_when_the_evaluation_model_cannot_be_built(self):
        with patch(_RESOLVE, side_effect=ModelConfigurationError("no key")):
            with pytest.raises(ModelNotConfiguredError) as exc_info:
                check_run_models(MagicMock(), MagicMock(), _config(), _plan(["rhesis", "sdk"]))

        assert exc_info.value.purpose == "evaluation"

    def test_checks_the_models_the_run_will_use(self):
        """The per-run overrides, not the user's defaults."""
        config = _config({"evaluation_model_id": "eval-id", "execution_model_id": "exec-id"})
        with patch(_RESOLVE) as resolve:
            check_run_models(MagicMock(), MagicMock(), config, _plan([], has_multi_turn=True))

        assert [(c.args[2], c.kwargs["override"]) for c in resolve.call_args_list] == [
            ("evaluation", "eval-id"),
            ("execution", "exec-id"),
        ]

    def test_a_rescore_of_multi_turn_tests_needs_no_execution_model(self):
        config = _config({"reference_test_run_id": "run-0", "is_rescore": True})
        with patch(_RESOLVE) as resolve:
            check_run_models(MagicMock(), MagicMock(), config, _plan([], has_multi_turn=True))

        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]


@pytest.mark.unit
class TestResolveRunModels:
    """The worker side: same rule, but a broken model falls back to the default."""

    def test_an_sdk_only_run_builds_no_model(self):
        with (
            patch(_RESOLVE) as resolve,
            patch(_DEFAULT) as default,
            patch(_GET_USER) as get_user,
            patch(_RECORD) as record,
        ):
            models = resolve_run_models(MagicMock(), _config(), _run(_plan(["sdk"])))

        resolve.assert_not_called()
        default.assert_not_called()
        get_user.assert_not_called()
        assert models.evaluation is None and models.execution is None
        assert record.call_args.kwargs["model_name"] is None

    def test_an_llm_metric_builds_only_the_evaluation_model(self):
        session, user = MagicMock(), MagicMock()
        judge = MagicMock(model_name="judge-1")
        config = _config({"evaluation_model_id": "eval-id"})
        with (
            patch(_RESOLVE, return_value=judge) as resolve,
            patch(_GET_USER, return_value=user),
            patch(_RECORD) as record,
        ):
            models = resolve_run_models(session, config, _run(_plan(["rhesis"])))

        resolve.assert_called_once_with(session, user, "evaluation", override="eval-id")
        assert models.evaluation is judge and models.execution is None
        assert record.call_args.kwargs["model_name"] == "judge-1"

    def test_multi_turn_builds_both(self):
        with (
            patch(_RESOLVE, side_effect=lambda _s, _u, purpose, override: purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            models = resolve_run_models(
                MagicMock(), _config(), _run(_plan(["sdk"], has_multi_turn=True))
            )

        assert sorted(c.args[2] for c in resolve.call_args_list) == ["evaluation", "execution"]
        assert (models.evaluation, models.execution) == ("evaluation", "execution")

    def test_a_replay_of_multi_turn_tests_builds_no_execution_model(self):
        with (
            patch(_RESOLVE, return_value="judge") as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            models = resolve_run_models(
                MagicMock(), _config(), _run(_plan([], has_multi_turn=True)), replay=True
            )

        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]
        assert models.execution is None

    def test_a_metric_that_became_llm_backed_after_dispatch_gets_its_judge(self):
        """The plan says SDK only, but the worker just resolved a judge metric."""
        with (
            patch(_RESOLVE, return_value="judge") as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            models = resolve_run_models(
                MagicMock(), _config(), _run(_plan(["sdk"])), live_backends=["sdk", "rhesis"]
            )

        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]
        assert models.evaluation == "judge" and models.execution is None

    def test_a_test_that_became_multi_turn_after_dispatch_gets_both_models(self):
        with (
            patch(_RESOLVE, side_effect=lambda _s, _u, purpose, override: purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            models = resolve_run_models(
                MagicMock(), _config(), _run(_plan(["sdk"])), live_multi_turn=True
            )

        assert sorted(c.args[2] for c in resolve.call_args_list) == ["evaluation", "execution"]
        assert (models.evaluation, models.execution) == ("evaluation", "execution")

    def test_a_replay_of_a_test_that_became_multi_turn_still_needs_no_execution_model(self):
        with (
            patch(_RESOLVE, return_value="judge") as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            models = resolve_run_models(
                MagicMock(), _config(), _run(_plan(["sdk"])), replay=True, live_multi_turn=True
            )

        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]
        assert models.execution is None

    def test_live_sdk_metrics_add_nothing(self):
        with patch(_RESOLVE) as resolve, patch(_RECORD):
            resolve_run_models(MagicMock(), _config(), _run(_plan(["sdk"])), live_backends=["sdk"])

        resolve.assert_not_called()

    def test_a_run_without_a_plan_builds_both(self):
        with (
            patch(_RESOLVE, return_value="model") as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            resolve_run_models(MagicMock(), _config(), _run(None))

        assert resolve.call_count == 2

    def test_a_broken_user_model_falls_back_to_the_default(self):
        session = MagicMock()
        with (
            patch(_RESOLVE, side_effect=ModelConfigurationError("no key")),
            patch(_DEFAULT, return_value="default-judge") as default,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            models = resolve_run_models(session, _config(), _run(_plan(["rhesis"])))

        assert default.call_count == 1
        assert default.call_args.args[1:] == (session, "org-1")
        assert models.evaluation == "default-judge"

    @pytest.mark.parametrize("user_id, found", [(None, None), ("user-1", None)])
    def test_no_resolvable_user_uses_the_default(self, user_id, found):
        with (
            patch(_RESOLVE) as resolve,
            patch(_DEFAULT, return_value="default-judge") as default,
            patch(_GET_USER, return_value=found),
            patch(_RECORD),
        ):
            models = resolve_run_models(
                MagicMock(), _config(user_id=user_id), _run(_plan(["rhesis"]))
            )

        resolve.assert_not_called()
        default.assert_called_once()
        assert models.evaluation == "default-judge"

    def test_quota_error_is_not_retried_against_the_default(self):
        with (
            patch(_RESOLVE, side_effect=_quota_error()),
            patch(_DEFAULT) as default,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            with pytest.raises(QuotaExceededError):
                resolve_run_models(MagicMock(), _config(), _run(_plan(["rhesis"])))

        default.assert_not_called()

"""Model readiness: can this user's default models be built, and what follows from it.

Covers the one readiness function (``check_model_readiness``) in the four setups
that matter, the onboarding defaults that depend on it, the auto-default when a
model becomes usable, and the background-embedding skip.

Deployment state is pinned per test rather than read from the environment: the
test session sets ``RHESIS_API_KEY`` for its own auth, and a developer's shell
may set ``ENABLE_RHESIS_KEY`` or ``DEFAULT_*_MODEL``.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from rhesis.backend.app import models
from rhesis.backend.app.crud.model import get_default_candidates, get_rhesis_system_models
from rhesis.backend.app.models.enums import ModelType
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services import model_setup
from rhesis.backend.app.services.embedding import services as embedding_services
from rhesis.backend.app.services.embedding.services import EmbeddingService
from rhesis.backend.app.services.model_setup import (
    adopt_platform_models,
    adopt_usable_defaults,
    apply_default_model_ids,
    onboarding_default_model_ids,
    readiness_for_request,
)
from rhesis.backend.app.utils.crud_utils import create_default_rhesis_model
from rhesis.backend.app.utils.model_errors import MODEL_NOT_CONFIGURED, ModelNotConfiguredError
from rhesis.backend.app.utils.user_model_utils import check_model_readiness, model_setup_problem

_UTILS = "rhesis.backend.app.utils.user_model_utils"
_PLATFORM_KEY = "rhesis.backend.app.services.platform_key"


@pytest.fixture
def deployment(monkeypatch):
    """Pin the deployment: ``deployment(cloud_key=..., platform_key_feature=...)``.

    ``cloud_key`` is this deployment's own ``RHESIS_API_KEY``, which is what makes
    the ``DEFAULT_*_MODEL`` settings buildable on Rhesis cloud.
    """
    patches = []

    def _set(*, cloud_key=None, platform_key_feature=False):
        if cloud_key:
            monkeypatch.setenv("RHESIS_API_KEY", cloud_key)
        else:
            monkeypatch.delenv("RHESIS_API_KEY", raising=False)
        for target, value in (
            (
                f"{_UTILS}.get_model_settings",
                SimpleNamespace(
                    generation_model="rhesis/rhesis",
                    evaluation_model="rhesis/rhesis",
                    execution_model="rhesis/rhesis",
                    embedding_model="rhesis/rhesis-embedding",
                ),
            ),
            (
                f"{_UTILS}.get_application_settings",
                SimpleNamespace(enable_rhesis_key=platform_key_feature),
            ),
            (f"{_PLATFORM_KEY}.get_rhesis_settings", SimpleNamespace(api_key=cloud_key)),
        ):
            p = patch(target, return_value=value)
            p.start()
            patches.append(p)

    yield _set
    for p in patches:
        p.stop()


@pytest.fixture
def rhesis_models(test_db, test_org_id, authenticated_user_id):
    """The seeded "Rhesis" language and embedding rows every org gets at onboarding."""
    common = dict(
        db=test_db,
        provider_value="rhesis",
        model_name="rhesis",
        icon="rhesis",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    language = create_default_rhesis_model(
        name="Rhesis Test", description="", model_type=ModelType.LANGUAGE.value, **common
    )
    embedding = create_default_rhesis_model(
        name="Rhesis Test Embedding",
        description="",
        model_type=ModelType.EMBEDDING.value,
        **common,
    )
    test_db.flush()
    return {"language_model_id": str(language.id), "embedding_model_id": str(embedding.id)}


@pytest.fixture
def own_model(test_db, test_org_id, authenticated_user_id, rhesis_models):
    """An org's own provider row: OpenAI with its own key."""
    from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

    provider = get_or_create_type_lookup(
        db=test_db,
        type_name="ProviderType",
        type_value="openai",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        commit=False,
    )
    model = models.Model(
        name="My OpenAI",
        model_name="gpt-4o",
        model_type=ModelType.LANGUAGE.value,
        key="sk-own-key",
        provider_type_id=provider.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        owner_id=authenticated_user_id,
    )
    test_db.add(model)
    test_db.flush()
    return model


@pytest.fixture
def jev_model(test_db, test_org_id, authenticated_user_id):
    """A Jev decision model: evaluation only, it can't generate text."""
    from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

    provider = get_or_create_type_lookup(
        db=test_db,
        type_name="ProviderType",
        type_value="jev",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        commit=False,
    )
    model = models.Model(
        name="My Jev",
        model_name="jev-latest",
        model_type="decision",
        key="ts-own-key",
        provider_type_id=provider.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        owner_id=authenticated_user_id,
    )
    test_db.add(model)
    test_db.flush()
    return model


@pytest.fixture
def user(authenticated_user):
    """The test user, with no model defaults set."""
    authenticated_user.user_settings = {"version": 1, "models": {}}
    return authenticated_user


def _set_platform_key(test_db, org_id, key):
    org = test_db.query(Organization).filter(Organization.id == org_id).first()
    org.rhesis_api_key = key
    test_db.flush()


@pytest.mark.integration
class TestCheckModelReadiness:
    def test_cloud_with_deployment_key_is_ready(self, test_db, user, rhesis_models, deployment):
        deployment(cloud_key="rh-cloud-key")
        apply_default_model_ids(user, onboarding_default_model_ids(test_db, user, rhesis_models))

        readiness = check_model_readiness(test_db, user)

        assert readiness.ready
        assert readiness.embedding is None

    def test_local_with_platform_key_is_ready(
        self, test_db, test_org_id, user, rhesis_models, deployment
    ):
        deployment(platform_key_feature=True)
        _set_platform_key(test_db, test_org_id, "rh-org-key")
        apply_default_model_ids(
            user,
            {
                "generation": rhesis_models["language_model_id"],
                "evaluation": rhesis_models["language_model_id"],
            },
        )

        assert check_model_readiness(test_db, user).ready

    def test_local_without_key_is_not_ready(self, test_db, user, rhesis_models, deployment):
        deployment(platform_key_feature=True)
        # The old onboarding data: pointed at the Rhesis rows with nothing to run them.
        apply_default_model_ids(
            user,
            {
                "generation": rhesis_models["language_model_id"],
                "evaluation": rhesis_models["language_model_id"],
                "embedding": rhesis_models["embedding_model_id"],
            },
        )

        readiness = check_model_readiness(test_db, user)

        assert not readiness.ready
        assert "Models page" in readiness.generation
        assert "RHESIS_API_KEY" not in readiness.generation
        assert readiness.embedding is not None

    def test_nothing_configured_without_key_is_not_ready(self, test_db, user, deployment):
        deployment(platform_key_feature=True)

        assert not check_model_readiness(test_db, user).ready

    def test_own_provider_is_ready_and_embedding_does_not_gate(
        self, test_db, user, own_model, deployment
    ):
        deployment(platform_key_feature=True)
        apply_default_model_ids(
            user, {"generation": str(own_model.id), "evaluation": str(own_model.id)}
        )

        readiness = check_model_readiness(test_db, user)

        assert readiness.ready
        # No embedding model and no key: reported, but models_ready stays True.
        assert readiness.embedding is not None

    def test_jev_evaluation_default_is_ready(self, test_db, user, own_model, jev_model, deployment):
        deployment(platform_key_feature=True)
        apply_default_model_ids(
            user, {"generation": str(own_model.id), "evaluation": str(jev_model.id)}
        )

        readiness = check_model_readiness(test_db, user)

        assert readiness.evaluation is None
        assert readiness.ready

    def test_jev_as_generation_default_is_not_ready(self, test_db, user, jev_model, deployment):
        deployment(platform_key_feature=True)
        apply_default_model_ids(
            user, {"generation": str(jev_model.id), "evaluation": str(jev_model.id)}
        )

        readiness = check_model_readiness(test_db, user)

        assert readiness.evaluation is None
        assert readiness.generation is not None
        assert not readiness.ready

    def test_readiness_for_request_uses_the_same_check(self, test_db, user, own_model, deployment):
        deployment(platform_key_feature=True)
        apply_default_model_ids(
            user, {"generation": str(own_model.id), "evaluation": str(own_model.id)}
        )

        assert readiness_for_request(test_db, user).ready

    def test_readiness_for_request_fails_open(self, test_db, user):
        with patch.object(model_setup, "check_model_readiness", side_effect=RuntimeError("boom")):
            assert readiness_for_request(test_db, user).ready

    def test_problem_carries_the_error_code_and_the_env_var_for_logs(
        self, test_db, user, deployment
    ):
        deployment(platform_key_feature=True)

        problem = model_setup_problem(test_db, user, "generation")

        assert isinstance(problem, ModelNotConfiguredError)
        assert problem.detail()["error_code"] == MODEL_NOT_CONFIGURED
        assert "DEFAULT_GENERATION_MODEL" in problem.log_message
        assert "\u2014" not in problem.message  # no em dash


@pytest.mark.integration
class TestOnboardingDefaults:
    def test_without_key_new_org_gets_no_defaults(self, test_db, user, rhesis_models, deployment):
        deployment(platform_key_feature=True)

        assert onboarding_default_model_ids(test_db, user, rhesis_models) == {}

    def test_with_key_new_org_keeps_todays_defaults(self, test_db, user, rhesis_models, deployment):
        deployment(cloud_key="rh-cloud-key")

        assert onboarding_default_model_ids(test_db, user, rhesis_models) == {
            "generation": rhesis_models["language_model_id"],
            "evaluation": rhesis_models["language_model_id"],
            "embedding": rhesis_models["embedding_model_id"],
        }


@pytest.mark.integration
class TestAdoptUsableDefaults:
    def test_own_model_fills_unusable_defaults(
        self, test_db, test_org_id, user, own_model, deployment
    ):
        deployment(platform_key_feature=True)

        adopt_usable_defaults(test_db, test_org_id, [own_model])

        test_db.refresh(user)
        assert user.settings.models.generation.model_id == own_model.id
        assert user.settings.models.evaluation.model_id == own_model.id
        assert check_model_readiness(test_db, user).ready

    def test_jev_only_fills_evaluation(self, test_db, test_org_id, user, jev_model, deployment):
        deployment(platform_key_feature=True)

        adopt_usable_defaults(test_db, test_org_id, [jev_model])

        test_db.refresh(user)
        assert user.settings.models.evaluation.model_id == jev_model.id
        assert not user.settings.models.generation.model_id

    def test_jev_then_language_model_fills_both(
        self, test_db, test_org_id, user, jev_model, own_model, deployment
    ):
        deployment(platform_key_feature=True)

        adopt_usable_defaults(test_db, test_org_id, [jev_model, own_model])

        test_db.refresh(user)
        assert user.settings.models.evaluation.model_id == jev_model.id
        assert user.settings.models.generation.model_id == own_model.id
        assert check_model_readiness(test_db, user).ready

    def test_db_error_does_not_break_the_outer_transaction(
        self, test_db, test_org_id, user, own_model
    ):
        def fail(db, *_):
            db.execute(sa.text("SELECT 1/0"))

        with patch.object(model_setup, "_adopt_for_user", side_effect=fail):
            adopt_usable_defaults(test_db, test_org_id, [own_model])

        assert test_db.execute(sa.text("SELECT 1")).scalar() == 1

    def test_usable_default_is_never_replaced(
        self, test_db, test_org_id, user, own_model, rhesis_models, deployment
    ):
        deployment(cloud_key="rh-cloud-key")
        apply_default_model_ids(
            user,
            {
                "generation": rhesis_models["language_model_id"],
                "evaluation": rhesis_models["language_model_id"],
            },
        )

        adopt_usable_defaults(test_db, test_org_id, [own_model])

        assert str(user.settings.models.generation.model_id) == rhesis_models["language_model_id"]

    def test_saving_a_platform_key_adopts_the_rhesis_models(
        self, test_db, test_org_id, user, rhesis_models, deployment
    ):
        deployment(platform_key_feature=True)
        assert not check_model_readiness(test_db, user).ready

        _set_platform_key(test_db, test_org_id, "rh-org-key")
        adopt_platform_models(test_db, user)

        test_db.refresh(user)
        # The shared test org may hold older seeded rows too; any of them will do.
        seeded = {"language": set(), "embedding": set()}
        for row in get_rhesis_system_models(test_db, test_org_id):
            seeded[row.model_type].add(str(row.id))
        assert str(user.settings.models.generation.model_id) in seeded["language"]
        assert str(user.settings.models.embedding.model_id) in seeded["embedding"]
        assert check_model_readiness(test_db, user).ready

    def test_creating_a_model_through_the_api_adopts_it(
        self, test_db, authenticated_client, user, own_model, deployment
    ):
        deployment(platform_key_feature=True)
        test_db.commit()

        response = authenticated_client.post(
            "/models/",
            json={
                "name": "Route OpenAI",
                "model_name": "gpt-4o-mini",
                "key": "sk-route-key",
                "provider_type_id": str(own_model.provider_type_id),
            },
        )

        assert response.status_code == 200, response.text
        test_db.refresh(user)
        assert str(user.settings.models.generation.model_id) == response.json()["id"]
        assert str(user.settings.models.evaluation.model_id) == response.json()["id"]


@pytest.mark.integration
class TestBackgroundEmbeddingSkip:
    def test_no_usable_embedder_skips_with_one_warning(
        self, test_db, test_org_id, user, rhesis_models, deployment, caplog
    ):
        deployment(platform_key_feature=True)
        apply_default_model_ids(user, {"embedding": rhesis_models["embedding_model_id"]})
        embedding_services._last_warned.pop(str(test_org_id), None)
        service = EmbeddingService(test_db)

        with patch.object(EmbeddingService, "execute_with_fallback") as run:
            for _ in range(3):
                assert (
                    service.enqueue_embedding(
                        entity_type="Test",
                        entity_id="00000000-0000-0000-0000-000000000001",
                        searchable_text="text",
                        user_id=str(user.id),
                        organization_id=str(test_org_id),
                    )
                    is False
                )

        run.assert_not_called()
        warnings = [r for r in caplog.records if "Skipping embeddings" in r.getMessage()]
        assert len(warnings) == 1
        assert not [r for r in caplog.records if r.levelname == "ERROR"]


@pytest.fixture
def second_model(test_db, test_org_id, authenticated_user_id, own_model):
    """Another usable model of the org's own, next to ``own_model``."""
    model = models.Model(
        name="My Second OpenAI",
        model_name="gpt-4o-mini",
        model_type=ModelType.LANGUAGE.value,
        key="sk-second-key",
        provider_type_id=own_model.provider_type_id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        owner_id=authenticated_user_id,
    )
    test_db.add(model)
    test_db.flush()
    return model


def _use_as_default(user, model):
    apply_default_model_ids(user, {"generation": str(model.id), "evaluation": str(model.id)})


def _delete_other_own_models(test_db, client, org_id, keep):
    """The shared test org may hold own models from earlier tests; remove them."""
    keep_ids = {m.id for m in keep}
    for model in get_default_candidates(test_db, org_id):
        if not model.is_protected and model.id not in keep_ids:
            assert client.delete(f"/models/{model.id}").status_code == 200


@pytest.mark.integration
class TestDeletingAModel:
    """Deleting the default must not strand a user who still has a working model."""

    def test_deleting_the_default_falls_back_to_a_remaining_model(
        self, test_db, test_org_id, authenticated_client, user, own_model, second_model, deployment
    ):
        deployment(platform_key_feature=True)
        _use_as_default(user, own_model)
        test_db.commit()
        _delete_other_own_models(
            test_db, authenticated_client, test_org_id, keep=[own_model, second_model]
        )

        response = authenticated_client.delete(f"/models/{own_model.id}")

        assert response.status_code == 200, response.text
        test_db.refresh(user)
        assert str(user.settings.models.generation.model_id) == str(second_model.id)
        assert str(user.settings.models.evaluation.model_id) == str(second_model.id)
        assert check_model_readiness(test_db, user).ready

    def test_deleting_the_last_usable_model_leaves_the_user_not_ready(
        self, test_db, test_org_id, authenticated_client, user, own_model, deployment
    ):
        deployment(platform_key_feature=True)
        _use_as_default(user, own_model)
        test_db.commit()
        _delete_other_own_models(test_db, authenticated_client, test_org_id, keep=[own_model])

        response = authenticated_client.delete(f"/models/{own_model.id}")

        assert response.status_code == 200, response.text
        test_db.refresh(user)
        assert not check_model_readiness(test_db, user).ready

    def test_deleting_another_model_leaves_a_working_default_alone(
        self, test_db, authenticated_client, user, own_model, second_model, deployment
    ):
        deployment(platform_key_feature=True)
        _use_as_default(user, own_model)
        test_db.commit()

        response = authenticated_client.delete(f"/models/{second_model.id}")

        assert response.status_code == 200, response.text
        test_db.refresh(user)
        assert str(user.settings.models.generation.model_id) == str(own_model.id)
        assert str(user.settings.models.evaluation.model_id) == str(own_model.id)
        assert check_model_readiness(test_db, user).ready

    def test_delete_with_working_defaults_builds_no_candidate(
        self, test_db, authenticated_client, user, own_model, second_model, deployment
    ):
        # The cloud key makes the deployment's embedding default work too.
        deployment(cloud_key="rh-cloud-key")
        _use_as_default(user, own_model)
        test_db.commit()

        with patch.object(
            model_setup, "model_setup_problem", wraps=model_setup.model_setup_problem
        ) as check:
            response = authenticated_client.delete(f"/models/{second_model.id}")

        assert response.status_code == 200, response.text
        # (db, user, purpose) checks a current default; a fourth argument builds a candidate.
        for_user = [c.args for c in check.call_args_list if c.args[1].id == user.id]
        assert sorted(args[2] for args in for_user) == ["embedding", "evaluation", "generation"]
        assert all(len(args) == 3 for args in for_user)

    def test_failing_candidate_query_does_not_fail_the_delete(
        self, test_db, authenticated_client, user, own_model, second_model, deployment
    ):
        deployment(platform_key_feature=True)
        _use_as_default(user, own_model)
        test_db.commit()

        def fail(db, *_):
            db.execute(sa.text("SELECT 1/0"))

        with patch.object(model_setup.model_crud, "get_default_candidates", side_effect=fail):
            response = authenticated_client.delete(f"/models/{own_model.id}")

        assert response.status_code == 200, response.text
        assert authenticated_client.get(f"/models/{own_model.id}").status_code == 410
        assert authenticated_client.get(f"/models/{second_model.id}").status_code == 200

    def test_candidates_put_own_language_models_first_and_skip_polyphemus(
        self, test_db, test_org_id, authenticated_user_id, own_model, jev_model, rhesis_models
    ):
        polyphemus = create_default_rhesis_model(
            db=test_db,
            provider_value="polyphemus",
            model_name="default",
            icon="polyphemus",
            name="Polyphemus Test",
            description="",
            model_type=ModelType.LANGUAGE.value,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.flush()

        ids = [str(m.id) for m in get_default_candidates(test_db, test_org_id)]

        assert ids.index(str(own_model.id)) < ids.index(str(jev_model.id))
        assert ids.index(str(jev_model.id)) < ids.index(rhesis_models["language_model_id"])
        assert str(polyphemus.id) not in ids

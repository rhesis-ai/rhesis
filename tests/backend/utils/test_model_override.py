"""
Unit tests for ``resolve_model`` and ``resolve_embedder`` in user_model_utils.

The parametrised suite covers every language purpose at once, which is the point
of taking purpose as an argument: generation, evaluation and execution share a
single code path, so they cannot drift apart the way three near-identical
functions could.

- No override, nothing configured -> the system default for that purpose
- No override, a configured model  -> that model
- An override                      -> the override wins over the configured one
- Either way, the org filter comes from the user, never from the caller
- And whatever the route, the caller gets a built model or an exception --
  never a bare provider string it has to finish constructing itself
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.user_model_utils import resolve_embedder, resolve_model
from rhesis.sdk.models.base import BaseLLM

LANGUAGE_PURPOSES = ["generation", "evaluation", "execution"]

_FETCH = "rhesis.backend.app.utils.user_model_utils._fetch_and_configure_model"
_DEFAULT = "rhesis.backend.app.utils.user_model_utils.resolve_default_hosted_model"
_FETCH_EMBEDDER = "rhesis.backend.app.utils.user_model_utils._fetch_and_configure_embedder"
_GET_MODEL = "rhesis.backend.app.utils.user_model_utils.get_model"
_LOAD_ROW = "rhesis.backend.app.utils.user_model_utils._load_model_row"
_BUILD = "rhesis.backend.app.utils.user_model_utils._build_configured_model"


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    user = Mock(spec=User)
    user.id = "user-123"
    user.email = "test@example.com"
    user.organization_id = "org-456"
    user.is_active = True
    user.is_verified = True
    user.settings.models = Mock()
    return user


def _configure(user, purpose, model_id):
    """Point the user's settings for *purpose* at *model_id* (None = unconfigured)."""
    setattr(user.settings.models, purpose, Mock(model_id=model_id))


@pytest.mark.unit
@pytest.mark.parametrize("purpose", LANGUAGE_PURPOSES)
class TestResolveModelOverride:
    def test_no_override_and_nothing_configured_uses_system_default(
        self, purpose, mock_db, mock_user
    ):
        _configure(mock_user, purpose, None)

        with patch(_DEFAULT, return_value="default-model") as mock_default:
            result = resolve_model(mock_db, mock_user, purpose)

        mock_default.assert_called_once_with(
            getattr(get_model_settings(), f"{purpose}_model"), mock_db, "org-456"
        )
        assert result == "default-model"

    def test_no_override_uses_the_users_configured_model(self, purpose, mock_db, mock_user):
        _configure(mock_user, purpose, "configured-model")

        with patch(_FETCH, return_value="from-settings") as mock_fetch:
            result = resolve_model(mock_db, mock_user, purpose)

        assert mock_fetch.call_args[1]["model_id"] == "configured-model"
        assert result == "from-settings"

    def test_override_calls_fetch_and_configure(self, purpose, mock_db, mock_user):
        _configure(mock_user, purpose, None)
        mock_llm = Mock()

        with patch(_FETCH, return_value=mock_llm) as mock_fetch:
            result = resolve_model(mock_db, mock_user, purpose, override="model-789")

        mock_fetch.assert_called_once_with(
            db=mock_db,
            model_id="model-789",
            organization_id="org-456",
            default_model=getattr(get_model_settings(), f"{purpose}_model"),
            user=mock_user,
        )
        assert result is mock_llm

    def test_override_wins_over_the_users_configured_model(self, purpose, mock_db, mock_user):
        _configure(mock_user, purpose, "configured-model")

        with patch(_FETCH, return_value="from-override") as mock_fetch:
            resolve_model(mock_db, mock_user, purpose, override="model-789")

        assert mock_fetch.call_args[1]["model_id"] == "model-789"

    def test_empty_string_override_falls_back_to_the_user_default(
        self, purpose, mock_db, mock_user
    ):
        """Empty string is falsy, so it must not count as an override."""
        _configure(mock_user, purpose, "configured-model")

        with patch(_FETCH, return_value="from-settings") as mock_fetch:
            result = resolve_model(mock_db, mock_user, purpose, override="")

        assert mock_fetch.call_args[1]["model_id"] == "configured-model"
        assert result == "from-settings"

    def test_override_uses_user_org_for_security(self, purpose, mock_db, mock_user):
        """An override id must be looked up under the user's own org, never a caller's."""
        _configure(mock_user, purpose, None)
        mock_user.organization_id = "secure-org-id"

        with patch(_FETCH, return_value="configured-model") as mock_fetch:
            resolve_model(mock_db, mock_user, purpose, override="any-model-id")

        assert mock_fetch.call_args[1]["organization_id"] == "secure-org-id"


@pytest.mark.unit
class TestResolveModelPurpose:
    def test_unknown_purpose_is_rejected(self, mock_db, mock_user):
        with pytest.raises(ValueError, match="Unknown model purpose"):
            resolve_model(mock_db, mock_user, "summarization")

    def test_embedding_is_not_a_language_purpose(self, mock_db, mock_user):
        """Embedders go through resolve_embedder -- see MODEL_PURPOSES."""
        with pytest.raises(ValueError, match="Unknown model purpose"):
            resolve_model(mock_db, mock_user, "embedding")


@pytest.mark.unit
class TestResolveModelAlwaysReturnsAModel:
    """The interface promise: a built model or an exception, never a string."""

    def test_no_configuration_builds_the_system_default(self, mock_db, mock_user):
        _configure(mock_user, "generation", None)
        built = Mock(spec=BaseLLM)

        with patch(_GET_MODEL, return_value=built) as mock_get_model:
            result = resolve_model(mock_db, mock_user, "generation")

        mock_get_model.assert_called_once_with(
            get_model_settings().generation_model, model_type="language"
        )
        assert result is built
        assert result.usage_metered is True

    def test_an_unbuildable_system_default_raises(self, mock_db, mock_user):
        """It used to hand back the bare string, which only moved the same
        failure to whichever call site got around to constructing it."""
        _configure(mock_user, "generation", None)

        with patch(_GET_MODEL, side_effect=ValueError("no such provider")):
            with pytest.raises(ValueError, match="no such provider"):
                resolve_model(mock_db, mock_user, "generation")


@pytest.mark.unit
class TestResolveEmbedder:
    def test_override_goes_to_the_embedder_path(self, mock_db, mock_user):
        """The purpose x shape matrix has no holes: an embedder takes an override too."""
        _configure(mock_user, "embedding", None)
        embedder = Mock()

        with patch(_FETCH_EMBEDDER, return_value=embedder) as mock_fetch:
            result = resolve_embedder(mock_db, mock_user, override="embed-1")

        mock_fetch.assert_called_once_with(
            db=mock_db,
            model_id="embed-1",
            organization_id="org-456",
            default_model=get_model_settings().embedding_model,
            dimensions=None,
        )
        assert result is embedder

    def test_no_configuration_builds_the_default_embedder(self, mock_db, mock_user):
        """No quota gate and no stamping: embedders emit no usage."""
        _configure(mock_user, "embedding", None)
        embedder = Mock()

        with patch(_DEFAULT) as mock_default, patch(_GET_MODEL, return_value=embedder) as mock_get:
            result = resolve_embedder(mock_db, mock_user)

        mock_default.assert_not_called()
        mock_get.assert_called_once_with(
            get_model_settings().embedding_model, model_type="embedding"
        )
        assert result is embedder

    def test_dimensions_reach_the_system_default(self, mock_db, mock_user):
        _configure(mock_user, "embedding", None)

        with patch(_GET_MODEL, return_value=Mock()) as mock_get:
            resolve_embedder(mock_db, mock_user, dimensions=768)

        assert mock_get.call_args[1]["dimensions"] == 768

    def test_dimensions_are_still_threaded_past_a_configured_row(self, mock_db, mock_user):
        """Not dead weight on this path: the row may be missing or keyless, and
        the default built in its place still has to come out the right width."""
        _configure(mock_user, "embedding", "configured-embedder")

        with patch(_FETCH_EMBEDDER, return_value=Mock()) as mock_fetch:
            resolve_embedder(mock_db, mock_user, dimensions=768)

        assert mock_fetch.call_args[1]["dimensions"] == 768

    def test_a_configured_row_is_built_at_its_own_width(self, mock_db, mock_user):
        """Where the docstring's claim actually bites: a row that resolves is
        built from its own stored settings, and never sees `dimensions`."""
        _configure(mock_user, "embedding", "configured-embedder")

        with (
            patch(_LOAD_ROW, return_value=Mock(provider_type=Mock(type_value="openai"))),
            patch(_BUILD, return_value=Mock()) as mock_build,
        ):
            resolve_embedder(mock_db, mock_user, dimensions=768)

        assert "dimensions" not in mock_build.call_args.kwargs
        assert 768 not in mock_build.call_args.args


@pytest.mark.unit
class TestResolveModelByUserId:
    """A user id principal resolves leniently -- background jobs must not die here."""

    def test_user_id_resolves_through_the_user(self, mock_db, mock_user):
        _configure(mock_user, "evaluation", "configured-model")
        built = Mock(spec=BaseLLM)

        with (
            patch(
                "rhesis.backend.app.crud.user.get_user_by_id", return_value=mock_user
            ) as mock_lookup,
            patch(_FETCH, return_value=built) as mock_fetch,
        ):
            result = resolve_model(mock_db, "user-123", "evaluation")

        mock_lookup.assert_called_once_with(mock_db, "user-123")
        assert mock_fetch.call_args[1]["model_id"] == "configured-model"
        assert result is built

    def test_missing_user_falls_back_to_a_built_system_default(self, mock_db):
        built = Mock(spec=BaseLLM)

        with (
            patch("rhesis.backend.app.crud.user.get_user_by_id", return_value=None),
            patch(_GET_MODEL, return_value=built) as mock_get_model,
        ):
            result = resolve_model(mock_db, "nobody", "execution")

        mock_get_model.assert_called_once_with(
            get_model_settings().execution_model, model_type="language"
        )
        assert result is built

    def test_a_failure_during_resolution_falls_back_to_a_built_system_default(
        self, mock_db, mock_user
    ):
        _configure(mock_user, "evaluation", "configured-model")
        built = Mock(spec=BaseLLM)

        with (
            patch("rhesis.backend.app.crud.user.get_user_by_id", return_value=mock_user),
            patch(_FETCH, side_effect=ValueError("bad key")),
            patch(_GET_MODEL, return_value=built),
        ):
            result = resolve_model(mock_db, "user-123", "evaluation")

        assert result is built

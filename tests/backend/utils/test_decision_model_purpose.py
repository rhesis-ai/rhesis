"""A decision model (Jev) resolves for evaluation and is refused for every other purpose."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.backend.app.utils.user_model_utils import resolve_model
from rhesis.sdk.models.providers.jev import JevDecisionModel

_FETCH = "rhesis.backend.app.utils.user_model_utils._fetch_and_configure_model"
_DEFAULT = "rhesis.backend.app.utils.user_model_utils.resolve_default_hosted_model"


@pytest.fixture
def user():
    user = Mock(spec=User)
    user.organization_id = "org-456"
    user.settings.models = Mock()
    for purpose in ("generation", "evaluation", "execution"):
        setattr(user.settings.models, purpose, Mock(model_id="model-1"))
    return user


@pytest.mark.unit
def test_jev_resolves_for_evaluation(user):
    jev = JevDecisionModel(api_key="key")
    with patch(_FETCH, return_value=jev):
        assert resolve_model(Mock(spec=Session), user, "evaluation") is jev


@pytest.mark.unit
@pytest.mark.parametrize("purpose", ["generation", "execution"])
def test_jev_is_refused_for_other_purposes(user, purpose):
    with patch(_FETCH, return_value=JevDecisionModel(api_key="key")):
        with pytest.raises(ModelConfigurationError, match=f"can't be used for {purpose}"):
            resolve_model(Mock(spec=Session), user, purpose)


@pytest.mark.unit
def test_jev_as_the_system_default_is_refused_for_generation(user):
    user.settings.models.generation = Mock(model_id=None)
    with patch(_DEFAULT, return_value=JevDecisionModel(api_key="key")):
        with pytest.raises(ModelConfigurationError, match="can't be used for generation"):
            resolve_model(Mock(spec=Session), user, "generation")

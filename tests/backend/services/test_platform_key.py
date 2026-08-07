"""Unit tests for the local-mode Rhesis platform API key service.

Covers the mockable logic without a real DB or network:
- key resolution precedence (org-stored key wins over the ``RHESIS_API_KEY`` env)
- masking (never exposes more than the last 4 chars)
- validation status-code mapping against the hosted platform
- the Polyphemus authorization probe (only an auth-enforcing response is
  conclusive; a public 200 is inconclusive)
"""

from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from rhesis.backend.app.services import platform_key as pk

_MODULE = "rhesis.backend.app.services.platform_key"


def _org(stored_key=None):
    org = Mock()
    org.rhesis_api_key = stored_key
    org.rhesis_key_valid = None
    org.rhesis_key_polyphemus_authorized = None
    org.rhesis_key_last_checked_at = None
    return org


def _model(provider: str | None):
    model = Mock()
    model.provider_type = Mock(type_value=provider) if provider else None
    return model


# --------------------------------------------------------------------------- #
# Masking
# --------------------------------------------------------------------------- #
def test_mask_key_shows_only_last_four():
    assert pk._mask_key("rh-secret-abcd1234").endswith("1234")
    assert "secret" not in pk._mask_key("rh-secret-abcd1234")


def test_mask_key_short_key_not_padded():
    assert pk._mask_key("ab") == "…ab"


# --------------------------------------------------------------------------- #
# Key resolution precedence (DB over env)
# --------------------------------------------------------------------------- #
def test_stored_key_wins_over_env():
    db = Mock(spec=Session)
    with (
        patch(f"{_MODULE}._load_org", return_value=_org("rh-stored")),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key="rh-env")),
    ):
        assert pk.get_platform_api_key(db, "org-1") == "rh-stored"


def test_env_key_used_when_no_stored_key():
    db = Mock(spec=Session)
    with (
        patch(f"{_MODULE}._load_org", return_value=_org(None)),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key="rh-env")),
    ):
        assert pk.get_platform_api_key(db, "org-1") == "rh-env"


def test_no_key_anywhere_is_absent():
    db = Mock(spec=Session)
    with (
        patch(f"{_MODULE}._load_org", return_value=_org(None)),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key=None)),
    ):
        assert pk.get_platform_api_key(db, "org-1") is None


# --------------------------------------------------------------------------- #
# get_availability_signals (single org lookup for presence + cached validation)
# --------------------------------------------------------------------------- #
def test_availability_signals_present_with_cached_validation():
    org = _org("rh-stored")
    org.rhesis_key_valid = True
    org.rhesis_key_polyphemus_authorized = False
    db = Mock(spec=Session)
    with (
        patch(f"{_MODULE}._load_org", return_value=org),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key=None)),
    ):
        assert pk.get_availability_signals(db, "org-1") == {
            "present": True,
            "key_valid": True,
            "polyphemus_authorized": False,
        }


def test_availability_signals_absent_when_no_key_anywhere():
    db = Mock(spec=Session)
    with (
        patch(f"{_MODULE}._load_org", return_value=_org(None)),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key=None)),
    ):
        assert pk.get_availability_signals(db, "org-1") == {
            "present": False,
            "key_valid": None,
            "polyphemus_authorized": None,
        }


def test_availability_signals_missing_org_fails_open():
    db = Mock(spec=Session)
    with (
        patch(f"{_MODULE}._load_org", return_value=None),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key=None)),
    ):
        assert pk.get_availability_signals(db, "org-1") == {
            "present": False,
            "key_valid": None,
            "polyphemus_authorized": None,
        }


# --------------------------------------------------------------------------- #
# annotate_model_availability
# --------------------------------------------------------------------------- #
def test_annotate_availability_outside_local_mode_everything_available():
    db = Mock(spec=Session)
    models = [_model("rhesis"), _model("openai")]
    with patch(f"{_MODULE}.get_application_settings", return_value=Mock(is_local=False)):
        pk.annotate_model_availability(db, "org-1", models)
    assert all(m.available is True and m.availability_reason is None for m in models)


def test_annotate_availability_local_mode_key_missing_greys_platform_providers():
    db = Mock(spec=Session)
    rhesis_model, poly_model, openai_model = (
        _model("rhesis"),
        _model("polyphemus"),
        _model("openai"),
    )
    with (
        patch(f"{_MODULE}.get_application_settings", return_value=Mock(is_local=True)),
        patch(f"{_MODULE}._load_org", return_value=_org(None)),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key=None)),
    ):
        pk.annotate_model_availability(db, "org-1", [rhesis_model, poly_model, openai_model])

    assert rhesis_model.available is False
    assert rhesis_model.availability_reason == "rhesis_key_missing"
    assert poly_model.available is False
    assert poly_model.availability_reason == "rhesis_key_missing"
    assert openai_model.available is True
    assert openai_model.availability_reason is None


def test_annotate_availability_local_mode_invalid_key_greys_platform_providers():
    db = Mock(spec=Session)
    org = _org("rh-stored")
    org.rhesis_key_valid = False
    rhesis_model = _model("rhesis")
    with (
        patch(f"{_MODULE}.get_application_settings", return_value=Mock(is_local=True)),
        patch(f"{_MODULE}._load_org", return_value=org),
    ):
        pk.annotate_model_availability(db, "org-1", [rhesis_model])

    assert rhesis_model.available is False
    assert rhesis_model.availability_reason == "rhesis_key_invalid"


def test_annotate_availability_local_mode_unauthorized_polyphemus_only():
    db = Mock(spec=Session)
    org = _org("rh-stored")
    org.rhesis_key_valid = True
    org.rhesis_key_polyphemus_authorized = False
    rhesis_model, poly_model = _model("rhesis"), _model("polyphemus")
    with (
        patch(f"{_MODULE}.get_application_settings", return_value=Mock(is_local=True)),
        patch(f"{_MODULE}._load_org", return_value=org),
    ):
        pk.annotate_model_availability(db, "org-1", [rhesis_model, poly_model])

    assert rhesis_model.available is True
    assert rhesis_model.availability_reason is None
    assert poly_model.available is False
    assert poly_model.availability_reason == "polyphemus_not_authorized"


def test_annotate_availability_local_mode_valid_key_everything_available():
    db = Mock(spec=Session)
    org = _org("rh-stored")
    org.rhesis_key_valid = True
    org.rhesis_key_polyphemus_authorized = True
    models = [_model("rhesis"), _model("polyphemus"), _model("openai")]
    with (
        patch(f"{_MODULE}.get_application_settings", return_value=Mock(is_local=True)),
        patch(f"{_MODULE}._load_org", return_value=org),
    ):
        pk.annotate_model_availability(db, "org-1", models)

    assert all(m.available is True and m.availability_reason is None for m in models)


def test_annotate_availability_unknown_validity_fails_open():
    """An unprobed RHESIS_API_KEY env key (valid=None) is never greyed."""
    db = Mock(spec=Session)
    rhesis_model = _model("rhesis")
    with (
        patch(f"{_MODULE}.get_application_settings", return_value=Mock(is_local=True)),
        patch(f"{_MODULE}._load_org", return_value=_org(None)),
        patch(f"{_MODULE}.get_rhesis_settings", return_value=Mock(api_key="rh-env")),
    ):
        pk.annotate_model_availability(db, "org-1", [rhesis_model])

    assert rhesis_model.available is True
    assert rhesis_model.availability_reason is None


# --------------------------------------------------------------------------- #
# validate_platform_key
# --------------------------------------------------------------------------- #
def test_validate_empty_key_is_invalid():
    assert pk.validate_platform_key("") == {"valid": False, "polyphemus_authorized": False}


def test_validate_ok_with_verified_owner():
    resp = Mock(status_code=200)
    resp.json.return_value = {"is_verified": True}
    with (
        patch(
            f"{_MODULE}.get_rhesis_settings", return_value=Mock(base_url="https://api.rhesis.ai")
        ),
        patch(f"{_MODULE}.httpx.get", return_value=resp),
    ):
        assert pk.validate_platform_key("rh-x") == {"valid": True, "polyphemus_authorized": True}


def test_validate_rejected_key():
    resp = Mock(status_code=401)
    with (
        patch(
            f"{_MODULE}.get_rhesis_settings", return_value=Mock(base_url="https://api.rhesis.ai")
        ),
        patch(f"{_MODULE}.httpx.get", return_value=resp),
    ):
        assert pk.validate_platform_key("rh-x") == {"valid": False, "polyphemus_authorized": False}


def test_validate_network_error_is_unknown():
    with (
        patch(
            f"{_MODULE}.get_rhesis_settings", return_value=Mock(base_url="https://api.rhesis.ai")
        ),
        patch(f"{_MODULE}.httpx.get", side_effect=Exception("boom")),
        patch(f"{_MODULE}._probe_polyphemus_authorized", return_value=None),
    ):
        assert pk.validate_platform_key("rh-x") == {"valid": None, "polyphemus_authorized": None}


# --------------------------------------------------------------------------- #
# _probe_polyphemus_authorized
# --------------------------------------------------------------------------- #
def test_probe_rejected_is_false():
    with patch(f"{_MODULE}.httpx.get", return_value=Mock(status_code=403)):
        assert pk._probe_polyphemus_authorized("rh-x") is False


def test_probe_public_200_is_inconclusive():
    with patch(f"{_MODULE}.httpx.get", return_value=Mock(status_code=200)):
        assert pk._probe_polyphemus_authorized("rh-x") is None


def test_probe_network_error_is_inconclusive():
    with patch(f"{_MODULE}.httpx.get", side_effect=Exception("boom")):
        assert pk._probe_polyphemus_authorized("rh-x") is None

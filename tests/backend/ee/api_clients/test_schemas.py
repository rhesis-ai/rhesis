"""Schema-level tests for :class:`AuthClientCreate` validators.

These pin the contract the CRUD router relies on. The most
security-relevant assertion is that ``expected_subject_audience`` is
required at the Pydantic layer, which closes the gap from the
security review (azp alone is insufficient on IdPs that share azp
across siblings, e.g. Keycloak service-account flows).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rhesis.backend.ee.api_clients.schemas import AuthClientCreate


def _valid_kwargs(**overrides):
    base = dict(
        client_id="brain",
        expected_subject_azp="brain-keycloak",
        expected_subject_audience="rhesis-api",
        allowed_scopes=["full"],
        default_scope="full",
    )
    base.update(overrides)
    return base


def test_minimal_valid_payload_accepted() -> None:
    obj = AuthClientCreate(**_valid_kwargs())
    assert obj.client_id == "brain"
    assert obj.expected_subject_audience == "rhesis-api"


def test_audience_is_required() -> None:
    with pytest.raises(ValidationError) as exc:
        AuthClientCreate(**_valid_kwargs(expected_subject_audience=None))
    msg = str(exc.value)
    assert "expected_subject_audience" in msg


def test_audience_rejects_empty_string() -> None:
    with pytest.raises(ValidationError) as exc:
        AuthClientCreate(**_valid_kwargs(expected_subject_audience=""))
    assert "expected_subject_audience" in str(exc.value)


def test_audience_rejects_omission() -> None:
    """Omitting the field entirely is rejected (``required=...`` field)."""
    kwargs = _valid_kwargs()
    kwargs.pop("expected_subject_audience")
    with pytest.raises(ValidationError) as exc:
        AuthClientCreate(**kwargs)
    assert "expected_subject_audience" in str(exc.value)


def test_default_scope_must_be_in_allowed_scopes() -> None:
    with pytest.raises(ValidationError):
        AuthClientCreate(
            **_valid_kwargs(allowed_scopes=["read"], default_scope="full")
        )

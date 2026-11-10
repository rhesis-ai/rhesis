"""A Model row must carry credentials of its own, checked when it is saved.

Every SDK provider falls back to reading its key from the process environment
when handed a falsy one (``litellm/main.py``: ``api_key or ... or
get_secret("OPENAI_API_KEY")``). A tenant row with neither a key nor an
endpoint therefore runs on this deployment's credentials: we pay the provider,
the tenant is not billed because the row is theirs, and to them it looks like
a working configuration.

Rejecting it at write time gives the tenant the error while they are still
looking at the form. ``_require_own_credentials`` in the resolution path is the
backstop for rows edited into this shape, or created before this check existed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.crud.model import _reject_rows_without_own_credentials

PROVIDER_TYPE_ID = "33333333-3333-3333-3333-333333333333"


def _db_returning(provider: str | None):
    """A session whose provider_type lookup yields *provider* (None = missing row)."""
    db = MagicMock()
    row = SimpleNamespace(type_value=provider) if provider is not None else None
    db.query.return_value.filter.return_value.first.return_value = row
    return db


def _row(*, key="", endpoint=None, provider_type_id=PROVIDER_TYPE_ID):
    return SimpleNamespace(
        name="my-model",
        key=key,
        endpoint=endpoint,
        provider_type_id=provider_type_id,
    )


@pytest.mark.parametrize("key", ["", "   "])
def test_rejects_a_row_with_no_key_and_no_endpoint(key):
    with pytest.raises(ValueError, match="needs an API key"):
        _reject_rows_without_own_credentials(_db_returning("openai"), _row(key=key, endpoint=None))


@pytest.mark.parametrize(
    "provider,key,endpoint",
    [
        ("openai", "sk-org-owned", None),
        ("vllm", "", "http://vllm.internal:8000"),
        ("vllm", None, "http://vllm.internal:8000"),
    ],
)
def test_allows_a_row_that_can_stand_on_its_own(provider, key, endpoint):
    """A key, or for a self-hosted server an endpoint: those commonly need no
    key at all, which is why an endpoint alone is enough there."""
    _reject_rows_without_own_credentials(_db_returning(provider), _row(key=key, endpoint=endpoint))


def test_rejects_an_endpoint_standing_in_for_a_key():
    """OpenAI reads its key from env when the row has none; the endpoint is ignored."""
    with pytest.raises(ValueError, match="needs an API key"):
        _reject_rows_without_own_credentials(
            _db_returning("openai"), _row(key="", endpoint="http://anything.example")
        )


@pytest.mark.parametrize("provider", ["rhesis", "polyphemus"])
def test_allows_rhesis_hosted_rows_with_neither(provider):
    """Running on our credentials with no key of its own is exactly what
    picking a Rhesis-hosted provider means, and it is billed accordingly."""
    _reject_rows_without_own_credentials(_db_returning(provider), _row(key="", endpoint=None))


def test_skips_the_check_when_no_provider_is_set():
    """Nothing to decide against, and the row cannot resolve to a model anyway."""
    _reject_rows_without_own_credentials(_db_returning("openai"), _row(provider_type_id=None))


def test_skips_the_check_when_the_provider_row_is_missing():
    """A dangling provider_type_id is a different error; do not mask it here."""
    _reject_rows_without_own_credentials(_db_returning(None), _row(key="", endpoint=None))


class TestUpdate:
    """The same check on the row an update would leave behind."""

    def _existing(self, **overrides):
        fields = {"name": "my-model", "key": "sk-org-owned", "endpoint": None}
        return SimpleNamespace(provider_type_id=PROVIDER_TYPE_ID, **{**fields, **overrides})

    def test_clearing_the_key_is_rejected(self):
        from rhesis.backend.app.crud.model import _reject_updates_without_own_credentials
        from rhesis.backend.app.schemas.model import ModelUpdate

        with pytest.raises(ValueError, match="needs an API key"):
            _reject_updates_without_own_credentials(
                _db_returning("openai"), self._existing(), ModelUpdate(key="")
            )

    def test_switching_to_vertex_with_an_api_key_is_rejected(self):
        from rhesis.backend.app.crud.model import _reject_updates_without_own_credentials
        from rhesis.backend.app.schemas.model import ModelUpdate

        with pytest.raises(ValueError, match="service-account"):
            _reject_updates_without_own_credentials(
                _db_returning("vertex_ai"),
                self._existing(),
                ModelUpdate(provider_type_id="44444444-4444-4444-8444-444444444444"),
            )

    def test_an_update_that_leaves_credentials_alone_is_not_checked(self):
        """A rename must not fail on a row that predates the check."""
        from rhesis.backend.app.crud.model import _reject_updates_without_own_credentials
        from rhesis.backend.app.schemas.model import ModelUpdate

        _reject_updates_without_own_credentials(
            _db_returning("openai"), self._existing(key=""), ModelUpdate(name="renamed")
        )

    def test_the_stored_key_counts_when_only_the_endpoint_changes(self):
        from rhesis.backend.app.crud.model import _reject_updates_without_own_credentials
        from rhesis.backend.app.schemas.model import ModelUpdate

        _reject_updates_without_own_credentials(
            _db_returning("openai"), self._existing(), ModelUpdate(endpoint="http://x.example")
        )

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
    with pytest.raises(ValueError, match="either an API key or an endpoint"):
        _reject_rows_without_own_credentials(_db_returning("openai"), _row(key=key, endpoint=None))


@pytest.mark.parametrize(
    "key,endpoint",
    [
        ("sk-org-owned", None),
        ("", "http://vllm.internal:8000"),
        (None, "http://vllm.internal:8000"),
    ],
)
def test_allows_a_row_that_can_stand_on_its_own(key, endpoint):
    """A key, or an endpoint. Self-hosted servers commonly need no key at all,
    which is why an endpoint alone is enough."""
    _reject_rows_without_own_credentials(_db_returning("openai"), _row(key=key, endpoint=endpoint))


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

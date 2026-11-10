"""Recycle bin access control and response hygiene.

- Permanent deletes (one item, empty bin) need ``recycle:purge``; reads need
  ``recycle:view``. Both are owner-only in community and Owner/Admin(/Auditor
  for view) in EE, so a plain member gets 403.
- Purge only applies to rows that are already soft-deleted.
- Purge of another org's row is a 404.
- Recycle responses never carry secret columns (encrypted values, hashes,
  credentials), for any model.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/security/test_recycle_authz.py -v
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.inspection import inspect

from rhesis.backend.app import models
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.services.recycle import secret_column_keys
from rhesis.backend.app.utils import crud_utils
from rhesis.backend.app.utils.encryption import EncryptedString
from tests.backend.fixtures.rls import scope_to_org
from tests.backend.fixtures.test_setup import create_test_organization_and_user
from tests.backend.security.test_authz_http_enforcement import _demote_to_member

CANARY_KEY = "sk-recycle-canary-0123456789"


def _context(test_db, *, owner: bool):
    """Fresh org + user + token; ``owner=False`` makes the user a plain member.

    Returns plain ids and headers: after the commit, ORM instances reload under
    whatever org the session is scoped to, and RLS hides other orgs' rows.
    """
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"Recycle AuthZ {suffix}",
        f"recycle_authz_{suffix}@rhesis-test.com",
        "Recycle AuthZ User",
    )
    if not owner:
        org.owner_id = None
        test_db.flush()
        _demote_to_member(test_db, org.id, user.id)
    ids = (str(org.id), str(user.id), {"Authorization": f"Bearer {token.token}"})
    test_db.commit()
    return ids


def _create_model(test_db, org_id, user_id, *, soft_delete: bool):
    scope_to_org(test_db, org_id)
    item = crud_utils.create_item(
        test_db,
        models.Model,
        {"name": f"recycle-{uuid.uuid4().hex[:6]}", "model_name": "gpt-x", "key": CANARY_KEY},
        organization_id=org_id,
        user_id=user_id,
    )
    item_id = item.id
    if soft_delete:
        crud_utils.delete_item(test_db, models.Model, item_id, organization_id=org_id)
    return item_id


def _model_row(test_db, org_id, item_id):
    scope_to_org(test_db, org_id)
    test_db.expire_all()
    return crud_utils.get_item(
        test_db, models.Model, item_id, organization_id=org_id, include_deleted=True
    )


@pytest.mark.integration
@pytest.mark.security
class TestRecyclePurgeAuthz:
    def test_member_cannot_purge_item(self, client, test_db):
        org, user, auth = _context(test_db, owner=False)
        item_id = _create_model(test_db, org, user, soft_delete=True)

        scope_to_org(test_db, org)
        resp = client.delete(f"/recycle/model/{item_id}?confirm=true", headers=auth)

        assert resp.status_code == 403, resp.text
        assert resp.headers.get("X-Accepted-Permissions") == "recycle:purge"
        assert _model_row(test_db, org, item_id) is not None

    def test_member_cannot_empty_bin(self, client, test_db):
        org, user, auth = _context(test_db, owner=False)
        item_id = _create_model(test_db, org, user, soft_delete=True)

        scope_to_org(test_db, org)
        resp = client.delete("/recycle/empty/model?confirm=true", headers=auth)

        assert resp.status_code == 403, resp.text
        assert _model_row(test_db, org, item_id) is not None

    def test_member_cannot_read_bin(self, client, test_db):
        org, user, auth = _context(test_db, owner=False)
        _create_model(test_db, org, user, soft_delete=True)

        scope_to_org(test_db, org)
        for path in ("/recycle/model", "/recycle/stats/counts"):
            resp = client.get(path, headers=auth)
            assert resp.status_code == 403, f"{path}: {resp.status_code} {resp.text}"
            assert CANARY_KEY not in resp.text

    def test_owner_can_purge_soft_deleted_item(self, client, test_db):
        org, user, auth = _context(test_db, owner=True)
        item_id = _create_model(test_db, org, user, soft_delete=True)

        scope_to_org(test_db, org)
        resp = client.delete(f"/recycle/model/{item_id}?confirm=true", headers=auth)

        assert resp.status_code == 200, resp.text
        assert _model_row(test_db, org, item_id) is None

    def test_owner_cannot_purge_live_item(self, client, test_db):
        org, user, auth = _context(test_db, owner=True)
        item_id = _create_model(test_db, org, user, soft_delete=False)

        scope_to_org(test_db, org)
        resp = client.delete(f"/recycle/model/{item_id}?confirm=true", headers=auth)

        assert resp.status_code == 404, resp.text
        row = _model_row(test_db, org, item_id)
        assert row is not None and row.deleted_at is None

    def test_owner_cannot_purge_other_org_item(self, client, test_db):
        other_org, other_user, _ = _context(test_db, owner=True)
        other_id = _create_model(test_db, other_org, other_user, soft_delete=True)
        org, _user, auth = _context(test_db, owner=True)

        scope_to_org(test_db, org)
        resp = client.delete(f"/recycle/model/{other_id}?confirm=true", headers=auth)

        assert resp.status_code == 404, resp.text
        assert _model_row(test_db, other_org, other_id) is not None


@pytest.mark.integration
@pytest.mark.security
class TestRecycleResponsesHideSecrets:
    def test_list_omits_model_key(self, client, test_db):
        org, user, auth = _context(test_db, owner=True)
        item_id = _create_model(test_db, org, user, soft_delete=True)

        scope_to_org(test_db, org)
        resp = client.get("/recycle/model", headers=auth)

        assert resp.status_code == 200, resp.text
        items = {i["id"]: i for i in resp.json()["items"]}
        assert str(item_id) in items
        assert "key" not in items[str(item_id)]
        assert "name" in items[str(item_id)]
        assert CANARY_KEY not in resp.text

    def test_restore_omits_model_key(self, client, test_db):
        org, user, auth = _context(test_db, owner=True)
        item_id = _create_model(test_db, org, user, soft_delete=True)

        scope_to_org(test_db, org)
        resp = client.post(f"/recycle/model/{item_id}/restore", headers=auth)

        assert resp.status_code == 200, resp.text
        assert resp.json()["item"]["id"] == str(item_id)
        assert "key" not in resp.json()["item"]
        assert CANARY_KEY not in resp.text


class TestSecretColumnRule:
    """The hide rule is generic, so a new secret column is covered without edits here."""

    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            (models.Model, {"key", "request_headers"}),
            (models.Endpoint, {"auth_token", "client_secret", "last_token", "auth"}),
            (models.Tool, {"credentials"}),
            (models.Token, {"token", "token_hash"}),
            (models.User, {"password_hash"}),
            (models.Organization, {"rhesis_api_key", "sso_config"}),
        ],
    )
    def test_known_secret_columns_hidden(self, model, expected):
        assert expected <= secret_column_keys(model)

    def test_refresh_token_hash_hidden(self):
        from rhesis.backend.app.models.refresh_token import RefreshToken

        assert "token_hash" in secret_column_keys(RefreshToken)

    def test_every_encrypted_column_hidden(self):
        for mapper in Base.registry.mappers:
            hidden = secret_column_keys(mapper.class_)
            for prop in inspect(mapper.class_).column_attrs:
                if isinstance(prop.columns[0].type, EncryptedString):
                    assert prop.key in hidden, f"{mapper.class_.__name__}.{prop.key}"

    def test_ordinary_columns_kept(self):
        hidden = secret_column_keys(models.Model)
        assert not {"id", "name", "model_name", "deleted_at", "organization_id"} & hidden

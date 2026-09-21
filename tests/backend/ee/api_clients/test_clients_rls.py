"""``authenticate_client`` must work for an app role subject to RLS.

``auth_client`` is FORCE ROW LEVEL SECURITY with a strict org-scoped policy and
no empty-org passthrough. Both callers (``/auth/token-exchange`` and the
client-bound ``/auth/refresh`` minter) reach it on ``get_db_session``, which
binds no tenant GUCs, so the lookup has to bind org scope itself or the row
stays invisible.

The test suite now runs as a non-BYPASSRLS role (``rhesis-app``), so RLS is
enforced by default. These tests blank the org GUC to simulate the unscoped
session ``get_db_session`` provides.

Migration ``f4a91c3e7b52`` wrapped the policy's cast in ``NULLIF``, so a blank
GUC now matches no rows instead of raising ``invalid input syntax for type
uuid: ""``. The security property is unchanged and the failure mode is better:
an unscoped read is denied rather than 500-ing.
"""

import uuid as _uuid

import pytest
from sqlalchemy import text

from rhesis.backend.ee.api_clients.clients import (
    AuthClient,
    authenticate_client,
    generate_client_secret,
    hash_client_secret,
)


@pytest.mark.integration
class TestAuthenticateClientUnderEnforcedRLS:
    def _make_client(self, test_db, org_id, secret):
        row = AuthClient(
            organization_id=org_id,
            client_id=f"probe-{_uuid.uuid4().hex[:8]}",
            client_secret_hash=hash_client_secret(secret),
            expected_subject_azp="probe-azp",
            expected_subject_audience="account",
            allowed_scopes=["read"],
            default_scope="read",
        )
        test_db.add(row)
        test_db.flush()
        return row

    def test_authenticates_for_a_role_subject_to_rls(self, test_db, test_organization):
        secret = generate_client_secret()
        row = self._make_client(test_db, test_organization.id, secret)
        client_id = row.client_id
        org_id = test_organization.id

        # Blank the org GUC so the session presents what get_db_session gives
        # the exchange. The test_db fixture's own org scope is still set at the
        # connection level; SET LOCAL overrides it within this savepoint only.
        test_db.execute(text("SET LOCAL app.current_organization = ''"))

        # authenticate_client binds org scope internally, so it resolves the
        # row even though the surrounding session has no tenant GUCs bound.
        result = authenticate_client(test_db, org_id, client_id, secret)
        assert result is not None, (
            "authenticate_client could not see auth_client under an RLS-enforced "
            "role -- the org scope binding regressed"
        )
        assert result.client_id == client_id

        # The raw unscoped query is what would have happened without the fix:
        # RLS hides the row rather than returning it to an unscoped caller.
        with test_db.begin_nested():
            test_db.execute(text("SET LOCAL app.current_organization = ''"))
            unscoped = test_db.execute(
                text("SELECT id FROM auth_client WHERE client_id = :c"),
                {"c": client_id},
            ).fetchone()
        assert unscoped is None, (
            "an unscoped session read an auth_client row -- the blank-org GUC "
            "must match nothing, not fall through to every tenant"
        )

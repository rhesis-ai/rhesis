"""``authenticate_client`` must work for an app role subject to RLS.

``auth_client`` is FORCE ROW LEVEL SECURITY with a strict
``organization_id = current_setting('app.current_organization')::uuid`` policy
and no empty-org passthrough. Both callers (``/auth/token-exchange`` and the
client-bound ``/auth/refresh`` minter) reach it on ``get_db_session``, which
binds no tenant GUCs, so the lookup has to bind org scope itself or it raises
``invalid input syntax for type uuid: ""``.

The test DB role is a superuser and bypasses RLS, so the sibling tests in
test_clients.py (which mock the session entirely) cannot catch this. These use a
real row and a real non-BYPASSRLS role -- the same technique as
``TestResolveUnderEnforcedRLS`` in tests/backend/routes/test_resolve.py.
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

        probe = f"authclient_rls_probe_{_uuid.uuid4().hex[:8]}"
        test_db.execute(text(f'CREATE ROLE "{probe}" NOLOGIN'))
        test_db.execute(text(f'GRANT SELECT ON public.auth_client TO "{probe}"'))
        test_db.execute(text(f'SET LOCAL ROLE "{probe}"'))

        # Blank the org GUC so the session presents what get_db_session gives the
        # exchange. Without this the fixture's own org scope is still bound and
        # the lookup would succeed regardless of the fix, making this vacuous.
        test_db.execute(text("SET LOCAL app.current_organization = ''"))

        # The function binds org scope internally, so it resolves the row even
        # though the surrounding session has no tenant GUCs bound.
        result = authenticate_client(test_db, org_id, client_id, secret)
        assert result is not None, (
            "authenticate_client could not see auth_client under an RLS-enforced "
            "role -- the org scope binding regressed"
        )
        assert result.client_id == client_id

        # And the raw unscoped query is what would have happened without it.
        with pytest.raises(Exception) as exc:
            with test_db.begin_nested():
                test_db.execute(text("SET LOCAL app.current_organization = ''"))
                test_db.execute(
                    text("SELECT id FROM auth_client WHERE client_id = :c"),
                    {"c": client_id},
                ).fetchone()
        assert 'invalid input syntax for type uuid: ""' in str(exc.value), (
            f"expected the empty-org uuid cast to fail, got: {exc.value}"
        )

        test_db.execute(text("RESET ROLE"))

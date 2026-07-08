"""Tests for :mod:`rhesis.backend.ee.licensing.mint`.

Round-trip tests: mint_token → verify_token → assert entitlements match the
tier catalog. Also covers edge cases for private-key absence, blanket-subject
rejection, custom overrides, and the dry-run flag.

The ``patch_public_keys`` autouse fixture from conftest.py ensures
verification uses the throwaway test keypair rather than the baked-in keys.
The ``ed25519_keypair`` fixture from conftest.py provides the same throwaway
keypair; here we additionally expose the *private* key as
``RHESIS_LICENSE_PRIVATE_KEY`` so mint_token can sign with it.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from rhesis.backend.app.features import FeatureName
from rhesis.backend.ee.licensing.entitlements import (
    BLANKET_SUBJECT,
    ENV_LICENSE_PRIVATE_KEY,
    LicenseEdition,
    LicenseStatus,
    LIMIT_SEATS,
)
from rhesis.backend.ee.licensing.tiers import EDITION_ENTITLEMENTS
from rhesis.backend.ee.licensing.verify import verify_token

pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "rhesis.backend.ee",
        reason="EE package not installed",
    ),
    reason="EE package not installed",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def private_key_env(ed25519_keypair, monkeypatch):
    """Expose the throwaway private key as RHESIS_LICENSE_PRIVATE_KEY.

    Pairs with the session-scoped ``patch_public_keys`` autouse fixture from
    conftest.py so mint and verify use the same throwaway keypair.
    """
    private_key, _ = ed25519_keypair
    pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    ).decode()
    monkeypatch.setenv(ENV_LICENSE_PRIVATE_KEY, pem)


# ---------------------------------------------------------------------------
# mint_token — round-trip tests per sellable edition
# ---------------------------------------------------------------------------


class TestMintTokenRoundTrip:
    """mint_token → verify_token produces entitlements that match the catalog."""

    ORG_ID = "00000000-0000-0000-0000-000000000042"

    def _mint_and_verify(self, edition: LicenseEdition) -> Any:
        from rhesis.backend.ee.licensing.mint import mint_token

        token = mint_token(
            org_id=self.ORG_ID,
            edition=edition,
            kid="test-v1",  # matches the throwaway key registered in conftest.py
        )
        ent = verify_token(token)
        assert ent is not None, f"verify_token returned None for edition={edition}"
        return ent

    def test_starter_round_trip(self, private_key_env):
        ent = self._mint_and_verify(LicenseEdition.STARTER)
        assert ent.edition is LicenseEdition.STARTER
        assert ent.status is LicenseStatus.ACTIVE
        assert ent.all_features is False
        assert ent.allows(FeatureName.SSO.value) is True
        assert ent.allows(FeatureName.API_CLIENTS.value) is False
        assert ent.limits == {LIMIT_SEATS: 5}
        assert ent.sub == self.ORG_ID

    def test_premium_round_trip(self, private_key_env):
        ent = self._mint_and_verify(LicenseEdition.PREMIUM)
        assert ent.edition is LicenseEdition.PREMIUM
        assert ent.allows(FeatureName.SSO.value) is True
        assert ent.allows(FeatureName.API_CLIENTS.value) is True
        assert ent.limits == {LIMIT_SEATS: 50}

    def test_enterprise_round_trip(self, private_key_env):
        ent = self._mint_and_verify(LicenseEdition.ENTERPRISE)
        assert ent.edition is LicenseEdition.ENTERPRISE
        assert ent.all_features is True
        assert ent.allows("any_future_feature") is True

    def test_master_round_trip(self, private_key_env):
        ent = self._mint_and_verify(LicenseEdition.MASTER)
        assert ent.edition is LicenseEdition.MASTER
        assert ent.all_features is True

    def test_trial_round_trip(self, private_key_env):
        ent = self._mint_and_verify(LicenseEdition.TRIAL)
        assert ent.edition is LicenseEdition.TRIAL
        assert ent.all_features is True
        assert ent.limits == {LIMIT_SEATS: 10}

    def test_all_sellable_editions_covered(self, private_key_env):
        """Ensure every edition in the catalog has been exercised above."""
        covered = {
            LicenseEdition.STARTER,
            LicenseEdition.PREMIUM,
            LicenseEdition.ENTERPRISE,
            LicenseEdition.MASTER,
            LicenseEdition.TRIAL,
        }
        assert covered == set(EDITION_ENTITLEMENTS.keys())


class TestMintTokenBlanket:
    def test_blanket_sub_verifies(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        token = mint_token(
            org_id=BLANKET_SUBJECT,
            edition=LicenseEdition.ENTERPRISE,
            kid="test-v1",
        )
        ent = verify_token(token)
        assert ent is not None
        assert ent.sub == BLANKET_SUBJECT
        assert ent.all_features is True


class TestMintTokenStandardClaims:
    """Standard JWT claims are stamped correctly."""

    ORG_ID = "00000000-0000-0000-0000-000000000099"

    def test_sub_is_org_id(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        ent = verify_token(
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")
        )
        assert ent is not None
        assert ent.sub == self.ORG_ID

    def test_jti_is_set_and_unique(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        ent1 = verify_token(
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")
        )
        ent2 = verify_token(
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")
        )
        assert ent1 is not None and ent2 is not None
        assert ent1.jti is not None
        assert ent2.jti is not None
        assert ent1.jti != ent2.jti

    def test_expiry_reflects_ttl_days(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        ent = verify_token(
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, ttl_days=30, kid="test-v1")
        )
        assert ent is not None
        assert ent.expires_at is not None
        now = datetime.now(tz=timezone.utc)
        delta = ent.expires_at - now
        # Allow ±60s clock slop but confirm the order-of-magnitude is 30 days.
        assert 29 * 86400 < delta.total_seconds() < 31 * 86400

    def test_status_is_passed_through(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        ent = verify_token(
            mint_token(
                self.ORG_ID,
                LicenseEdition.PREMIUM,
                status=LicenseStatus.PAST_DUE,
                kid="test-v1",
            )
        )
        assert ent is not None
        assert ent.status is LicenseStatus.PAST_DUE


# ---------------------------------------------------------------------------
# Custom overrides
# ---------------------------------------------------------------------------


class TestMintTokenOverrides:
    ORG_ID = "00000000-0000-0000-0000-000000000007"

    def test_custom_features_override_tier_defaults(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        ent = verify_token(
            mint_token(
                self.ORG_ID,
                LicenseEdition.STARTER,
                kid="test-v1",
                custom_features=["sso", "api_clients"],
            )
        )
        assert ent is not None
        assert ent.all_features is False
        assert ent.allows("sso") is True
        assert ent.allows("api_clients") is True

    def test_custom_limits_merge_with_tier_defaults(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        ent = verify_token(
            mint_token(
                self.ORG_ID,
                LicenseEdition.PREMIUM,
                kid="test-v1",
                custom_limits={"seats": 200, "extra_quota": 50},
            )
        )
        assert ent is not None
        assert ent.limits["seats"] == 200
        assert ent.limits["extra_quota"] == 50

    def test_custom_limits_override_tier_seat_count(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        ent = verify_token(
            mint_token(
                self.ORG_ID,
                LicenseEdition.STARTER,
                kid="test-v1",
                custom_limits={LIMIT_SEATS: 99},
            )
        )
        assert ent is not None
        assert ent.limits[LIMIT_SEATS] == 99


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestMintTokenErrors:
    ORG_ID = "00000000-0000-0000-0000-000000000001"

    def test_missing_private_key_raises(self, monkeypatch):
        monkeypatch.delenv(ENV_LICENSE_PRIVATE_KEY, raising=False)
        from rhesis.backend.ee.licensing.mint import mint_token

        with pytest.raises(RuntimeError, match=ENV_LICENSE_PRIVATE_KEY):
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")

    def test_empty_private_key_raises(self, monkeypatch):
        monkeypatch.setenv(ENV_LICENSE_PRIVATE_KEY, "   ")
        from rhesis.backend.ee.licensing.mint import mint_token

        with pytest.raises(RuntimeError, match=ENV_LICENSE_PRIVATE_KEY):
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")

    def test_invalid_pem_raises(self, monkeypatch):
        monkeypatch.setenv(ENV_LICENSE_PRIVATE_KEY, "not-a-pem")
        from rhesis.backend.ee.licensing.mint import mint_token

        with pytest.raises(RuntimeError):
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")

    def test_base64_encoded_pem_is_accepted(self, ed25519_keypair, monkeypatch):
        """A base64-encoded PEM is accepted identically to a raw PEM."""
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )

        private_key, _ = ed25519_keypair
        pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        ).decode()
        b64_pem = base64.b64encode(pem.encode()).decode()
        monkeypatch.setenv(ENV_LICENSE_PRIVATE_KEY, b64_pem)

        from rhesis.backend.ee.licensing.mint import mint_token

        token = mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")
        ent = verify_token(token)
        assert ent is not None
        assert ent.edition == LicenseEdition.ENTERPRISE

    def test_invalid_base64_content_raises(self, monkeypatch):
        """A non-PEM string that is valid base64 but decodes to garbage raises RuntimeError."""
        junk_b64 = base64.b64encode(b"this is not a pem").decode()
        monkeypatch.setenv(ENV_LICENSE_PRIVATE_KEY, junk_b64)
        from rhesis.backend.ee.licensing.mint import mint_token

        with pytest.raises(RuntimeError):
            mint_token(self.ORG_ID, LicenseEdition.ENTERPRISE, kid="test-v1")

    def test_non_sellable_edition_raises(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        with pytest.raises(KeyError):
            mint_token(self.ORG_ID, LicenseEdition.COMMUNITY, kid="test-v1")

    def test_unknown_edition_raises(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import mint_token

        with pytest.raises(KeyError):
            mint_token(self.ORG_ID, LicenseEdition.UNKNOWN, kid="test-v1")


# ---------------------------------------------------------------------------
# issue() — DB write path
# ---------------------------------------------------------------------------


class TestIssue:
    ORG_ID = "00000000-0000-0000-0000-000000000011"

    def _make_db(self):
        """Return a mock Session with a fake Organization row."""
        org = MagicMock()
        org.id = self.ORG_ID
        org.license = None

        db = MagicMock()
        db.query.return_value.filter.return_value.one.return_value = org
        return db, org

    def test_dry_run_returns_token_without_writing(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import issue

        db, org = self._make_db()
        token = issue(
            db,
            org_id=self.ORG_ID,
            edition=LicenseEdition.ENTERPRISE,
            kid="test-v1",
            dry_run=True,
        )
        assert token
        ent = verify_token(token)
        assert ent is not None
        assert ent.sub == self.ORG_ID
        # DB must not have been touched
        db.commit.assert_not_called()
        assert org.license is None

    def test_live_issue_writes_and_commits(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import issue

        db, org = self._make_db()

        # bind_scope_to_session is imported lazily inside issue() so we patch
        # it at its source module rather than on the mint module namespace.
        with patch(
            "rhesis.backend.app.database.bind_scope_to_session"
        ) as mock_bind:
            token = issue(
                db,
                org_id=self.ORG_ID,
                edition=LicenseEdition.ENTERPRISE,
                kid="test-v1",
                dry_run=False,
            )

        mock_bind.assert_called_once_with(db, organization_id=self.ORG_ID)
        assert org.license == token
        db.commit.assert_called_once()

    def test_live_issue_is_idempotent(self, private_key_env):
        """Calling issue twice overwrites the token — no uniqueness error."""
        from rhesis.backend.ee.licensing.mint import issue

        db, org = self._make_db()
        with patch("rhesis.backend.app.database.bind_scope_to_session"):
            token1 = issue(
                db,
                org_id=self.ORG_ID,
                edition=LicenseEdition.ENTERPRISE,
                kid="test-v1",
            )
        with patch("rhesis.backend.app.database.bind_scope_to_session"):
            token2 = issue(
                db,
                org_id=self.ORG_ID,
                edition=LicenseEdition.ENTERPRISE,
                kid="test-v1",
            )
        # Both tokens are valid; jti differs so they are distinct
        ent1 = verify_token(token1)
        ent2 = verify_token(token2)
        assert ent1 is not None and ent2 is not None
        assert ent1.jti != ent2.jti

    def test_blanket_subject_rejected(self, private_key_env):
        from rhesis.backend.ee.licensing.mint import issue

        db, _ = self._make_db()
        with pytest.raises(ValueError, match=r"\*"):
            issue(db, org_id=BLANKET_SUBJECT, edition=LicenseEdition.ENTERPRISE)

    def test_returned_token_verifies(self, private_key_env):
        """The token returned by issue() passes verify_token."""
        from rhesis.backend.ee.licensing.mint import issue

        db, _ = self._make_db()
        with patch("rhesis.backend.app.database.bind_scope_to_session"):
            token = issue(
                db,
                org_id=self.ORG_ID,
                edition=LicenseEdition.TRIAL,
                kid="test-v1",
            )
        ent = verify_token(token)
        assert ent is not None
        assert ent.edition is LicenseEdition.TRIAL
        assert ent.sub == self.ORG_ID

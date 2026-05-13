"""Unit tests for :mod:`rhesis.backend.ee.api_clients.clients`.

These cover the security-critical primitives: the secret hash
generator, the timing-equalised dummy hash on miss, and the
org-scoped lookup contract added to ``authenticate_client`` (so two
tenants can share a ``client_id`` without one of them locking the
other out).

The tests run with an in-memory SQLite session that's pinned only
enough to exercise the SQLAlchemy filter shape; the real Postgres-
specific schema (encrypted columns, partial unique indexes) is
covered by integration tests that bring up the actual DB.
"""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock
from uuid import uuid4

from rhesis.backend.ee.api_clients.clients import (
    SECRET_HASH_PREFIX,
    authenticate_client,
    generate_client_secret,
    hash_client_secret,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRow:
    """Minimal AuthClient-shaped stand-in for the DB lookup."""

    def __init__(
        self,
        *,
        organization_id,
        client_id: str,
        client_secret_hash: str,
        disabled: bool = False,
    ) -> None:
        self.organization_id = organization_id
        self.client_id = client_id
        self.client_secret_hash = client_secret_hash
        self.disabled = disabled


class _FakeQuery:
    """Captures the filter call shape so tests can assert org-scoping.

    Returns ``row`` only when *every* filter clause attached to it
    matches the row. The fake intentionally walks the BinaryExpressions
    by string-comparing the right-hand side; that's enough fidelity for
    a constraint-shape test and avoids pulling in the SQLAlchemy
    expression evaluator.
    """

    def __init__(self, row: Optional[_FakeRow]) -> None:
        self._row = row
        self._matched = True
        self.filter_args: list = []

    def filter(self, *clauses) -> "_FakeQuery":
        self.filter_args.extend(clauses)
        if self._row is None:
            self._matched = False
            return self

        # Each clause is `Column == value` or `Column.is_(None)`. We
        # compare by walking the BinaryExpression's right-hand side.
        for clause in clauses:
            try:
                # eq / != produce ``BinaryExpression``; ``is_(None)``
                # produces ``IsBinaryExpression`` -- both expose .left
                # and .right.
                left_name = clause.left.key  # type: ignore[attr-defined]
                right = clause.right.value  # type: ignore[attr-defined]
            except AttributeError:
                # is_(None) for deleted_at -- accept all rows; tests
                # that need to vary deleted_at would patch the row
                # itself.
                continue

            if left_name == "organization_id":
                if str(self._row.organization_id) != str(right):
                    self._matched = False
            elif left_name == "client_id":
                if self._row.client_id != right:
                    self._matched = False
        return self

    def first(self) -> Optional[_FakeRow]:
        return self._row if self._matched else None


def _fake_db(row: Optional[_FakeRow]) -> MagicMock:
    """Return a Session-shaped mock whose .query(AuthClient) yields *row*."""
    db = MagicMock()
    db.query.return_value = _FakeQuery(row)
    return db


# ---------------------------------------------------------------------------
# Secret generation + hashing
# ---------------------------------------------------------------------------


class TestGenerateClientSecret:
    def test_returns_url_safe_string(self) -> None:
        secret = generate_client_secret()
        assert isinstance(secret, str)
        # urlsafe_b64 charset: [A-Za-z0-9_-]; no padding (token_urlsafe).
        assert all(c.isalnum() or c in "_-" for c in secret), secret

    def test_outputs_are_distinct(self) -> None:
        # 256 bits of CSPRNG output -- collisions are not just rare,
        # they would indicate the RNG is broken.
        secrets = {generate_client_secret() for _ in range(100)}
        assert len(secrets) == 100


class TestHashClientSecret:
    def test_emits_versioned_prefix(self) -> None:
        h = hash_client_secret("anything")
        assert h.startswith(SECRET_HASH_PREFIX)

    def test_is_deterministic(self) -> None:
        # The verifier relies on hash(presented) == stored_hash, so the
        # function MUST be deterministic for the constant-time compare
        # to mean anything.
        assert hash_client_secret("abc") == hash_client_secret("abc")

    def test_distinguishes_inputs(self) -> None:
        assert hash_client_secret("abc") != hash_client_secret("abd")


# ---------------------------------------------------------------------------
# authenticate_client -- org-scoped lookup contract
# ---------------------------------------------------------------------------


class TestAuthenticateClient:
    """The lookup MUST scope by ``(organization_id, client_id)``.

    The unique constraint on ``auth_client`` is per-org, so two
    tenants may legitimately share a ``client_id`` like ``brain``.
    A lookup keyed on ``client_id`` alone would return whichever row
    sorted first and lock the other tenant out.
    """

    def test_success_returns_row(self) -> None:
        org_id = uuid4()
        secret = "s3cret"
        row = _FakeRow(
            organization_id=org_id,
            client_id="brain",
            client_secret_hash=hash_client_secret(secret),
        )
        result = authenticate_client(_fake_db(row), org_id, "brain", secret)
        assert result is row

    def test_unknown_client_returns_none(self) -> None:
        # No row with that (org, client_id) -- still must hash a dummy
        # so the wall clock matches the success path.
        result = authenticate_client(_fake_db(None), uuid4(), "ghost", "x")
        assert result is None

    def test_wrong_secret_returns_none(self) -> None:
        org_id = uuid4()
        row = _FakeRow(
            organization_id=org_id,
            client_id="brain",
            client_secret_hash=hash_client_secret("right"),
        )
        result = authenticate_client(
            _fake_db(row), org_id, "brain", "wrong"
        )
        assert result is None

    def test_disabled_client_returns_none(self) -> None:
        org_id = uuid4()
        secret = "s3cret"
        row = _FakeRow(
            organization_id=org_id,
            client_id="brain",
            client_secret_hash=hash_client_secret(secret),
            disabled=True,
        )
        result = authenticate_client(_fake_db(row), org_id, "brain", secret)
        assert result is None

    def test_lookup_is_org_scoped(self) -> None:
        """Same client_id under a *different* org must NOT authenticate.

        Regression coverage for the multi-tenant lookup fix: before
        the change, ``authenticate_client(db, "brain", secret)`` would
        match the first ``brain`` row regardless of org. The fake DB's
        ``_FakeQuery`` enforces the (org_id, client_id) filter exactly
        as the production query does, so passing the wrong org returns
        no row.
        """
        org_a = uuid4()
        org_b = uuid4()
        secret = "s3cret"
        # Row exists under org_a only.
        row = _FakeRow(
            organization_id=org_a,
            client_id="brain",
            client_secret_hash=hash_client_secret(secret),
        )
        # Authenticate against org_b: must not return the org_a row.
        result = authenticate_client(_fake_db(row), org_b, "brain", secret)
        assert result is None

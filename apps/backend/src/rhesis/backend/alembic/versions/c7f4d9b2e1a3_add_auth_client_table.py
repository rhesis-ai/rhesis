"""add auth_client table

Per-organization OAuth2 / RFC 8693 client credentials table used by the
``API_CLIENTS`` EE feature. Each row is bound to one ``organization``
via ``ON DELETE CASCADE`` so disabling a tenant tears down their
clients without leaving orphans.

Schema notes (each maps to the model in
``ee/backend/src/rhesis/backend/ee/api_clients/clients.py``):

- ``client_id`` is unique per-organization, so two orgs may both have a
  ``brain`` client. The check pattern matches ``^[a-z0-9][a-z0-9_-]{2,63}$``.
- ``client_secret_hash`` stores ``"sha256:<64 hex>"`` plaintext at the
  application layer; the column itself is wrapped at the ORM layer in
  ``EncryptedString`` (Fernet, ``DB_ENCRYPTION_KEY``) so the on-disk
  bytes are ciphertext, not the hash. The version prefix lets us
  migrate to a different hash function later without ambiguity in
  stored values. Because the raw column is encrypted, no SQL CHECK
  on the prefix is possible -- the prefix invariant holds at the
  application layer in ``ee/.../api_clients/clients.py``.
- ``allowed_scopes`` is a Postgres ``text[]`` so the CHECK constraint
  ``default_scope = ANY(allowed_scopes)`` runs in pure SQL and the
  invariant holds at rest, not just at the application layer.
- ``token_epoch`` is the lever for **coarse revocation**. Bumping it
  invalidates every Rhesis JWT issued before that instant because
  ``verify_jwt_token`` enforces ``iat >= epoch``. No DB lookup needed
  at verify time.
- ``name`` has a partial unique index (``WHERE name IS NOT NULL``) so
  the UI table never surfaces two indistinguishable rows but multiple
  rows without a name remain legal.

Idempotent guards (``IF NOT EXISTS``-style information_schema lookups)
mirror the SSO migrations so re-running on a partially-applied DB does
not error.

Revision ID: c7f4d9b2e1a3
Revises: fe4a8b2c9d1e
Create Date: 2026-05-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "c7f4d9b2e1a3"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CLIENT_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{2,63}$"


def upgrade() -> None:
    conn = op.get_bind()

    table_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name='auth_client'"
        )
    ).fetchone()

    if not table_exists:
        op.create_table(
            "auth_client",
            sa.Column(
                "id",
                sa.dialects.postgresql.UUID(),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("nano_id", sa.String(), nullable=True, unique=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column(
                "organization_id",
                sa.dialects.postgresql.UUID(),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("client_id", sa.String(64), nullable=False),
            # The hash is stored at rest as Fernet ciphertext via the
            # ORM-side EncryptedString TypeDecorator. The SQL column
            # type is unbounded String/Text because Fernet output length
            # is variable (and tied to the hash length).
            sa.Column("client_secret_hash", sa.String(), nullable=False),
            sa.Column("expected_subject_azp", sa.String(255), nullable=False),
            sa.Column("expected_subject_audience", sa.String(255), nullable=True),
            sa.Column("name", sa.String(120), nullable=True),
            sa.Column("allowed_scopes", ARRAY(sa.Text()), nullable=False),
            sa.Column("default_scope", sa.String(255), nullable=False),
            sa.Column(
                "token_epoch",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "disabled",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "organization_id",
                "client_id",
                name="uq_auth_client_org_client",
            ),
            sa.CheckConstraint(
                "default_scope = ANY(allowed_scopes)",
                name="ck_auth_client_default_scope_allowed",
            ),
            sa.CheckConstraint(
                f"client_id ~ '{CLIENT_ID_PATTERN}'",
                name="ck_auth_client_client_id_pattern",
            ),
            # No SQL CHECK on the client_secret_hash prefix: the column
            # is Fernet-encrypted at rest via EncryptedString, so the
            # 'sha256:' prefix is invisible to the database. The prefix
            # invariant is enforced after decryption by
            # ee/.../api_clients/clients.py:_verify_secret_hash.
        )

    index_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='auth_client' "
            "AND indexname='ix_auth_client_organization_id'"
        )
    ).fetchone()
    if not index_exists:
        op.create_index(
            "ix_auth_client_organization_id",
            "auth_client",
            ["organization_id"],
        )

    deleted_at_index_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='auth_client' "
            "AND indexname='ix_auth_client_deleted_at'"
        )
    ).fetchone()
    if not deleted_at_index_exists:
        op.create_index(
            "ix_auth_client_deleted_at",
            "auth_client",
            ["deleted_at"],
        )

    # Partial unique index on (organization_id, name) WHERE name IS NOT NULL.
    # Two rows with name=NULL are still allowed; two rows with the same
    # non-null name within an org are not. SQLAlchemy's UniqueConstraint
    # cannot express the WHERE clause in DDL, so we use a partial index.
    name_index_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='auth_client' "
            "AND indexname='uq_auth_client_org_name'"
        )
    ).fetchone()
    if not name_index_exists:
        op.create_index(
            "uq_auth_client_org_name",
            "auth_client",
            ["organization_id", "name"],
            unique=True,
            postgresql_where=sa.text("name IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("uq_auth_client_org_name", table_name="auth_client")
    op.drop_index("ix_auth_client_deleted_at", table_name="auth_client")
    op.drop_index("ix_auth_client_organization_id", table_name="auth_client")
    op.drop_table("auth_client")

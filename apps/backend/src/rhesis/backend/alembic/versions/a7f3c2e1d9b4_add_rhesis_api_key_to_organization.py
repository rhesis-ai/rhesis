"""Add rhesis_api_key to organization

Adds an org-scoped Rhesis platform API key (encrypted at rest via the
application-layer ``EncryptedString`` type, so the stored column is a plain
string of ciphertext) plus cached validation results (validity and Polyphemus
authorization) and a timestamp caching when that key was last validated
against the hosted platform. The cached results let status reads and the GET
/models availability annotation avoid re-probing the network on every call.
Used by the local-mode ``/platform`` endpoints so self-hosted deployments can
set the platform key per organization instead of only via the
``RHESIS_API_KEY`` env var.

Revision ID: a7f3c2e1d9b4
Revises: e90c29496562
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7f3c2e1d9b4"
down_revision: Union[str, None] = "e90c29496562"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization",
        sa.Column(
            "rhesis_api_key",
            sa.String(),
            nullable=True,
            comment="Encrypted org-scoped Rhesis platform API key (local mode)",
        ),
    )
    op.add_column(
        "organization",
        sa.Column(
            "rhesis_key_valid",
            sa.Boolean(),
            nullable=True,
            comment="Cached result of the last platform key validation",
        ),
    )
    op.add_column(
        "organization",
        sa.Column(
            "rhesis_key_polyphemus_authorized",
            sa.Boolean(),
            nullable=True,
            comment="Cached Polyphemus authorization from the last validation",
        ),
    )
    op.add_column(
        "organization",
        sa.Column(
            "rhesis_key_last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the stored platform key was last validated",
        ),
    )


def downgrade() -> None:
    op.drop_column("organization", "rhesis_key_last_checked_at")
    op.drop_column("organization", "rhesis_key_polyphemus_authorized")
    op.drop_column("organization", "rhesis_key_valid")
    op.drop_column("organization", "rhesis_api_key")

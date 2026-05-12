"""merge parallel heads after SSO rebase onto embedding table

Revision ID: fe4a8b2c9d1e
Revises: c2e4f8a91b0d, b4c5d6e7f8a9
Create Date: 2026-05-12

SSO migrations (a3b4c5d6e7f8 -> b4c5d6e7f8a9) were rebased onto a1b2c3d4e5f8,
leaving c2e4f8a91b0d without children. This empty merge joins the two tips so
``alembic upgrade head`` is unambiguous again.
"""

from typing import Sequence, Union

revision: str = "fe4a8b2c9d1e"
down_revision: Union[str, None] = ("c2e4f8a91b0d", "b4c5d6e7f8a9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

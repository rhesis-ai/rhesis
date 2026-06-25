"""merge RBAC and Azure DevOps parallel heads

Revision ID: f0a1b2c3d4e5
Revises: a0b1c2d3e4f5, ad0c2e7f9b14
Create Date: 2026-06-24

The Azure DevOps provider migration (ad0c2e7f9b14) and the RBAC/token-scoping
chain (7d8e9f0a1b2c -> a0b1c2d3e4f5) both forked from a033c0a601a3. This empty
merge restores a single head so ``alembic upgrade head`` is unambiguous again.
"""

from typing import Sequence, Union

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = ("a0b1c2d3e4f5", "ad0c2e7f9b14")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

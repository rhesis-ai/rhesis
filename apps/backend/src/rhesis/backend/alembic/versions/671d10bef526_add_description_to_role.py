"""Add description column to role table and backfill built-in role descriptions.

Adds a ``description`` TEXT column (non-null, default '') to ``role`` and fills
in human-readable descriptions for the five built-in roles so the frontend can
display them without hard-coding strings.  Custom role rows are left with an
empty string — the UI handles that gracefully.

Revision ID: 671d10bef526
Revises: c0d1e2f3a4b5
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "671d10bef526"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Descriptions for the five built-in roles.
# Kept self-contained here (not imported from models.py) so this migration
# remains stable even if the application code evolves.
# The canonical reference copy also lives in BUILT_IN_ROLE_DESCRIPTIONS in
# ee/backend/src/rhesis/backend/ee/rbac/models.py.
# To update copy: write a new migration with UPDATE statements.
_BUILT_IN_DESCRIPTIONS: list[tuple[str, str]] = [
    (
        "Owner",
        "Complete control of the organization, including billing, "
        "deletion, and ownership transfer.",
    ),
    (
        "Admin",
        "Manage members, roles, projects, and organization settings. "
        "Cannot delete the organization.",
    ),
    (
        "Member",
        "Create, edit, and run evaluations across their projects. Manage their own API tokens.",
    ),
    (
        "Viewer",
        "Read-only access to all resources. Can browse and export but cannot make changes.",
    ),
    (
        "None",
        "No access. Explicitly revoke a member while keeping them in the organization.",
    ),
]


def upgrade() -> None:
    op.add_column(
        "role",
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE role SET description = :description WHERE name = :name AND is_built_in = true"
        ),
        [{"name": name, "description": desc} for name, desc in _BUILT_IN_DESCRIPTIONS],
    )


def downgrade() -> None:
    op.drop_column("role", "description")

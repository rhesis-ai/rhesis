"""cleanup_stale_user_settings_fields

Remove stale camelCase onboarding fields that were incorrectly stored
at the top level of user_settings JSONB. These fields (usersInvited,
endpointSetup, projectCreated, testCasesCreated) belong nested under
the 'onboarding' key in snake_case format. Their presence at the root
level causes Pydantic validation errors (extra fields not permitted).

Fixes: https://github.com/rhesis-ai/rhesis/issues/1323

Revision ID: f1a2b3c4d5e6
Revises: c0974af513a6
Create Date: 2026-02-12 12:00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "1776e6dd47d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stale camelCase keys that should not exist at the top level of user_settings
STALE_KEYS = [
    "usersInvited",
    "endpointSetup",
    "projectCreated",
    "testCasesCreated",
]


def upgrade() -> None:
    """Remove stale camelCase onboarding fields from user_settings JSONB."""
    for key in STALE_KEYS:
        op.execute(
            f"UPDATE \"user\" SET user_settings = user_settings - '{key}' "
            f"WHERE user_settings ? '{key}'"
        )


def downgrade() -> None:
    """No-op: we don't want to restore stale data."""
    pass

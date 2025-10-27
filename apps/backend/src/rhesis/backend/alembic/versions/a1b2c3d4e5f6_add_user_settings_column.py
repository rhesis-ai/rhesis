"""add_user_settings_column

Revision ID: a1b2c3d4e5f6
Revises: f8b3c9d4e5a6
Create Date: 2025-10-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f8b3c9d4e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_settings column for storing user preferences and settings.

    The user_settings column stores user preferences as JSONB with structure:
    - version: Schema version for future migrations
    - models: Model preferences for generation and evaluation
      - generation: Settings for test generation (model_id, temperature, etc.)
      - evaluation: Settings for LLM-as-judge evaluation
    - ui: UI preferences (theme, density, sidebar, page size)
    - notifications: Email and in-app notification preferences
    - localization: Language, timezone, date/time formats
    - privacy: Privacy settings

    This enables users to customize their experience and set default models
    for different use cases.
    """
    # Add user_settings column with default structure
    op.add_column(
        "user",
        sa.Column(
            "user_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{"version": 1, "models": {"generation": {}, "evaluation": {}}}',
        ),
    )


def downgrade() -> None:
    """Remove user_settings column."""
    op.drop_column("user", "user_settings")

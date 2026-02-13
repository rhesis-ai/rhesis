"""Update model_type from 'llm' to 'language'

Revision ID: update_model_type_llm_to_language
Revises: fe5d9ca98fca
Create Date: 2026-02-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "update_model_type_llm_to_language"
down_revision: Union[str, None] = "fe5d9ca98fca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing 'llm' values to 'language'
    op.execute(
        """
        UPDATE model
        SET model_type = 'language'
        WHERE model_type = 'llm'
        """
    )

    # Update the server default for new rows
    op.alter_column(
        "model",
        "model_type",
        server_default="language",
        existing_type=sa.String(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Revert 'language' values back to 'llm'
    op.execute(
        """
        UPDATE model
        SET model_type = 'llm'
        WHERE model_type = 'language'
        """
    )

    # Revert the server default
    op.alter_column(
        "model",
        "model_type",
        server_default="llm",
        existing_type=sa.String(),
        existing_nullable=False,
    )

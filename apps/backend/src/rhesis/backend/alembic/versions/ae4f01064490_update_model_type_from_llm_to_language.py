from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis



# revision identifiers, used by Alembic.
revision: str = 'ae4f01064490'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
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

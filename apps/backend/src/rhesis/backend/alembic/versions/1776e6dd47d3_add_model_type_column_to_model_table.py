from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis


# revision identifiers, used by Alembic.
revision: str = "1776e6dd47d3"
down_revision: Union[str, None] = "c0974af513a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model",
        sa.Column(
            "model_type",
            sa.String(),
            nullable=False,
            server_default="llm",
        ),
    )


def downgrade() -> None:
    op.drop_column("model", "model_type")

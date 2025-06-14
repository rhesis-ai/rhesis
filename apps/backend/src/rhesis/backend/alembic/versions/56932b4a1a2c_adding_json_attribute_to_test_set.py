from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import rhesis.backend

# revision identifiers, used by Alembic.
revision: str = "56932b4a1a2c"
down_revision: Union[str, None] = "f6de20bdb01d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("test_result", sa.Column("user_id", rhesis.app.models.guid.GUID(), nullable=True))
    op.alter_column(
        "test_result",
        "test_metrics",
        existing_type=sa.TEXT(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="test_metrics::jsonb",
        existing_nullable=True,
    )
    op.create_foreign_key(None, "test_result", "user", ["user_id"], ["id"])
    op.add_column("test_set", sa.Column("user_id", rhesis.app.models.guid.GUID(), nullable=True))
    op.add_column(
        "test_set", sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.create_foreign_key(None, "test_set", "user", ["user_id"], ["id"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "test_set", type_="foreignkey")
    op.drop_column("test_set", "attributes")
    op.drop_column("test_set", "user_id")
    op.drop_constraint(None, "test_result", type_="foreignkey")
    op.alter_column(
        "test_result",
        "test_metrics",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.drop_column("test_result", "user_id")
    # ### end Alembic commands ###

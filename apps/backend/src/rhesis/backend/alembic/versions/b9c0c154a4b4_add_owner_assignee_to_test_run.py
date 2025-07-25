from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import rhesis.backend

# revision identifiers, used by Alembic.
revision: str = "b9c0c154a4b4"
down_revision: Union[str, None] = "8fe9702e0729"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("test_run", sa.Column("owner_id", rhesis.app.models.guid.GUID(), nullable=True))
    op.add_column(
        "test_run", sa.Column("assignee_id", rhesis.app.models.guid.GUID(), nullable=True)
    )
    op.create_foreign_key(None, "test_run", "user", ["owner_id"], ["id"])
    op.create_foreign_key(None, "test_run", "user", ["assignee_id"], ["id"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "test_run", type_="foreignkey")
    op.drop_constraint(None, "test_run", type_="foreignkey")
    op.drop_column("test_run", "assignee_id")
    op.drop_column("test_run", "owner_id")
    # ### end Alembic commands ###

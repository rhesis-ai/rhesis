from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import rhesis.backend

# revision identifiers, used by Alembic.
revision: str = "f6de20bdb01d"
down_revision: Union[str, None] = "889f1405866c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "test_set", sa.Column("license_type_id", rhesis.app.models.guid.GUID(), nullable=True)
    )
    op.create_foreign_key(None, "test_set", "type_lookup", ["license_type_id"], ["id"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("test_set_license_type_id_fkey", "test_set", type_="foreignkey")
    op.drop_column("test_set", "license_type_id")
    # ### end Alembic commands ###

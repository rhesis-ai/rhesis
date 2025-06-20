from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f2f0f1d9c201'
down_revision: Union[str, None] = 'd6a128541142'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('test_configuration', sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.alter_column('test_run', 'test_configuration_id',
               existing_type=sa.UUID(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('test_run', 'test_configuration_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.drop_column('test_configuration', 'attributes')
    # ### end Alembic commands ###
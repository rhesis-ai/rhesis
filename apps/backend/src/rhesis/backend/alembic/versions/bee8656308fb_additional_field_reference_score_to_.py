from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis



# revision identifiers, used by Alembic.
revision: str = 'bee8656308fb'
down_revision: Union[str, None] = '69d0da1f9c31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('metric', sa.Column('reference_score', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('metric', 'reference_score')
    # ### end Alembic commands ###
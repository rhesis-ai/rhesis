from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis



# revision identifiers, used by Alembic.
revision: str = '6dec7c5469b6'
down_revision: Union[str, None] = '1d482debe2c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('metric', sa.Column('evaluation_examples', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('metric', 'evaluation_examples')
    # ### end Alembic commands ###
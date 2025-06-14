from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ae95a2982195'
down_revision: Union[str, None] = 'bee8656308fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('endpoint', sa.Column('auth_type', sa.String(), nullable=True))
    op.add_column('endpoint', sa.Column('token', sa.Text(), nullable=True))
    op.add_column('endpoint', sa.Column('client_id', sa.Text(), nullable=True))
    op.add_column('endpoint', sa.Column('client_secret', sa.Text(), nullable=True))
    op.add_column('endpoint', sa.Column('token_url', sa.Text(), nullable=True))
    op.add_column('endpoint', sa.Column('scopes', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('endpoint', sa.Column('audience', sa.Text(), nullable=True))
    op.add_column('endpoint', sa.Column('extra_payload', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('endpoint', 'extra_payload')
    op.drop_column('endpoint', 'audience')
    op.drop_column('endpoint', 'scopes')
    op.drop_column('endpoint', 'token_url')
    op.drop_column('endpoint', 'client_secret')
    op.drop_column('endpoint', 'client_id')
    op.drop_column('endpoint', 'token')
    op.drop_column('endpoint', 'auth_type')
    # ### end Alembic commands ###
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence



# revision identifiers, used by Alembic.
revision: str = '4df7965dfdfb'
down_revision: Union[str, None] = ('a939dc9b4168', 'c5e102239786')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
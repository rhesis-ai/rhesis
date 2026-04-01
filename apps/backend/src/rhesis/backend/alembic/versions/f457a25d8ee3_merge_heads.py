from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis



# revision identifiers, used by Alembic.
revision: str = 'f457a25d8ee3'
down_revision: Union[str, None] = ('533ebb47f308', '8993eecbb913')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

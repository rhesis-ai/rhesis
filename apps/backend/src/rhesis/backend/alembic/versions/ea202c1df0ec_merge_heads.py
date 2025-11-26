from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis


# revision identifiers, used by Alembic.
revision: str = "ea202c1df0ec"
down_revision: Union[str, None] = ("dc03001dbf24", "f25f0800e881")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "7274a152f6c1"
down_revision: Union[str, None] = ("a1b2c3d4e5f7", "e8dd05d20cd0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

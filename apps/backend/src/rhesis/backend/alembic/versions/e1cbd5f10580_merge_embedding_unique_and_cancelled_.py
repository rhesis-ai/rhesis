from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "e1cbd5f10580"
down_revision: Union[str, None] = ("8993eecbb913", "a1b2c3d4e5f9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

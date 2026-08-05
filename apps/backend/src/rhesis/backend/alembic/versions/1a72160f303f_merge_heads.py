from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "1a72160f303f"
down_revision: Union[str, None] = ("7dd69fe35db5", "a7f3c2e1d9b4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

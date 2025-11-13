from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "179eb8de14f1"
down_revision: Union[str, None] = ("8a2f3b4c5d6e", "f9763398493e")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

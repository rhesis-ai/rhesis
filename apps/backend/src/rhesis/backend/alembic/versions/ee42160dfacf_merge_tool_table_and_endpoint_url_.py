from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "ee42160dfacf"
down_revision: Union[str, None] = ("dc03001dbf24", "f25f0800e881")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

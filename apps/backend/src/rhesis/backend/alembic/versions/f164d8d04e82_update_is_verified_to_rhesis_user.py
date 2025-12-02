from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f164d8d04e82"
down_revision: Union[str, None] = "faad9078ee78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE \"user\" SET is_verified = true WHERE email LIKE '%@rhesis.ai'")


def downgrade() -> None:
    op.execute("UPDATE \"user\" SET is_verified = false WHERE email LIKE '%@rhesis.ai'")

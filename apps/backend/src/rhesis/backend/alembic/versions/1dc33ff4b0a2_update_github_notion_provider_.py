from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1dc33ff4b0a2"
down_revision: Union[str, None] = "7b998a6fe52d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE type_lookup
        SET description = 'GitHub integration'
        WHERE type_name = 'ToolProviderType'
        AND type_value = 'github'
        AND deleted_at IS NULL
        """
    )

    op.execute(
        """
        UPDATE type_lookup
        SET description = 'Notion integration'
        WHERE type_name = 'ToolProviderType'
        AND type_value = 'notion'
        AND deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE type_lookup
        SET description = 'GitHub repository integration'
        WHERE type_name = 'ToolProviderType'
        AND type_value = 'github'
        AND deleted_at IS NULL
        """
    )

    op.execute(
        """
        UPDATE type_lookup
        SET description = 'Notion workspace integration'
        WHERE type_name = 'ToolProviderType'
        AND type_value = 'notion'
        AND deleted_at IS NULL
        """
    )

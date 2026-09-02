"""Add Trello ToolProviderType
Revision ID: b6723e65f233
Revises: 105b0268e6a4
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "b6723e65f233"
down_revision: Union[str, None] = "105b0268e6a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_type_values = """
        ('ToolProviderType', 'trello', 'Trello integration')
    """
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM tool
        WHERE tool_provider_type_id IN (
            SELECT id FROM type_lookup
            WHERE type_name = 'ToolProviderType' AND type_value = 'trello'
        );
        """
    )
    op.execute(load_cleanup_type_lookup_template("ToolProviderType", "'trello'"))

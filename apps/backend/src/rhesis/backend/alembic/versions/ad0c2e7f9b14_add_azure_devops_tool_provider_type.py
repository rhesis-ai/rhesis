"""Add Azure DevOps ToolProviderType

Revision ID: ad0c2e7f9b14
Revises: a0b1c2d3e4f5
Create Date: 2026-06-19

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

revision: str = "ad0c2e7f9b14"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_type_values = """
        ('ToolProviderType', 'azure_devops', 'Azure DevOps integration')
    """
    op.execute(load_type_lookup_template(provider_type_values))


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM tool
        WHERE tool_provider_type_id IN (
            SELECT id FROM type_lookup
            WHERE type_name = 'ToolProviderType' AND type_value = 'azure_devops'
        );
        """
    )
    op.execute(load_cleanup_type_lookup_template("ToolProviderType", "'azure_devops'"))

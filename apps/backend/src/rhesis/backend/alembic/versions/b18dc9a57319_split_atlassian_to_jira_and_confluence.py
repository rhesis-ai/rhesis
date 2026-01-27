from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "b18dc9a57319"
down_revision: Union[str, None] = "6a7b8c9d0e1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_type_values = """
        ('ToolProviderType', 'jira', 'Jira integration'),
        ('ToolProviderType', 'confluence', 'Confluence integration')
    """

    # Step 1: Add new provider types
    op.execute(load_type_lookup_template(provider_type_values))

    # Step 2: Delete all tools that use the atlassian provider type
    op.execute(
        """
        DELETE FROM tool
        WHERE tool_provider_type_id = (
            SELECT id FROM type_lookup
            WHERE type_name = 'ToolProviderType' AND type_value = 'atlassian'
        );
        """
    )

    # Step 3: Delete atlassian provider type
    op.execute(load_cleanup_type_lookup_template("ToolProviderType", "'atlassian'"))


def downgrade() -> None:
    # Step 1: Re-add atlassian provider type
    op.execute(
        load_type_lookup_template(
            "('ToolProviderType', 'atlassian', 'Atlassian integration for Jira and Confluence')"
        )
    )

    # Step 2: Delete new provider types
    op.execute(load_cleanup_type_lookup_template("ToolProviderType", "'jira', 'confluence'"))

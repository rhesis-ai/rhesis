from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import rhesis.backend.app.models.guid as guid_module
from rhesis.backend.alembic.utils.template_loader import load_type_lookup_template

# revision identifiers, used by Alembic.
revision: str = "bffb5364a019"
down_revision: Union[str, None] = "de50496b2a9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Update Source model with comments support, file management, and metadata.

    Changes:
    - Add CommentsMixin and CountsMixin support to Source model
    - Rename entity_type to source_type_id with foreign key to type_lookup
    - Add content field for raw text content from source
    - Add source_metadata JSONB field for file metadata
     (file_path, file_type, file_size, file_hash, uploaded_at)
    - Add citation and language_code fields
    - Add source_id foreign key to test table
    - Update comment and task models to support 'Source' entity_type
    """
    # Step 1: Add EntityType "Source" to type_lookup table
    entity_type_values = "('EntityType', 'Source', 'Entity type for sources')"
    op.execute(load_type_lookup_template(entity_type_values))

    # Step 2: Add SourceType entries to type_lookup table
    source_type_values = """
        ('SourceType', 'Document', 'Document source (PDF, Word, etc.)'),
        ('SourceType', 'Website', 'Website or web page source'),
        ('SourceType', 'API', 'API documentation or response'),
        ('SourceType', 'Database', 'Database schema or data source'),
        ('SourceType', 'Code', 'Source code or repository'),
        ('SourceType', 'Manual', 'Manual or user-provided content')
    """.strip()
    op.execute(load_type_lookup_template(source_type_values))

    # Step 3: Add content field to source table
    op.add_column("source", sa.Column("content", sa.Text(), nullable=True))

    # Rename entity_type to source_type_id and add foreign key
    op.alter_column("source", "entity_type", new_column_name="source_type_id")
    op.alter_column("source", "source_type_id", type_=guid_module.GUID())
    op.create_foreign_key(
        "fk_source_source_type_id", "source", "type_lookup", ["source_type_id"], ["id"]
    )

    # Add citation and language_code fields
    op.add_column("source", sa.Column("citation", sa.Text(), nullable=True))
    op.add_column(
        "source",
        sa.Column(
            "language_code",
            sa.String(5),
            nullable=True,
            comment="Language in IETF language tag format",
        ),
    )

    # Add source_metadata JSONB field
    op.add_column(
        "source",
        sa.Column("source_metadata", sa.dialects.postgresql.JSONB(), nullable=True, default=dict),
    )

    # Add source_id foreign key to test table
    op.add_column("test", sa.Column("source_id", guid_module.GUID(), nullable=True))
    op.create_foreign_key("fk_test_source_id", "test", "source", ["source_id"], ["id"])


def downgrade() -> None:
    """
    Revert Source model changes.
    """
    # Remove source_id foreign key from test table
    op.drop_constraint("fk_test_source_id", "test", type_="foreignkey")
    op.drop_column("test", "source_id")

    # Remove source_metadata field
    op.drop_column("source", "source_metadata")

    # Remove citation and language_code fields
    op.drop_column("source", "language_code")
    op.drop_column("source", "citation")

    # Revert source_type_id back to entity_type
    op.drop_constraint("fk_source_source_type_id", "source", type_="foreignkey")
    op.alter_column("source", "source_type_id", new_column_name="entity_type")
    op.alter_column("source", "entity_type", type_=sa.String())

    # Remove content field
    op.drop_column("source", "content")

    # Step 1: Remove SourceType entries from type_lookup table
    source_type_values = "'Document', 'Website', 'API', 'Database', 'Code', 'Manual'"
    op.execute(f"""
        DELETE FROM type_lookup
        WHERE type_name = 'SourceType'
        AND type_value IN ({source_type_values})
    """)

    # Step 2: Remove EntityType "Source" from type_lookup table
    op.execute("""
        DELETE FROM type_lookup
        WHERE type_name = 'EntityType'
        AND type_value = 'Source'
    """)

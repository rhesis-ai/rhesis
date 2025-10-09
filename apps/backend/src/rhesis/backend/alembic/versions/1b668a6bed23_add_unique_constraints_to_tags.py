from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence



# revision identifiers, used by Alembic.
revision: str = '1b668a6bed23'
down_revision: Union[str, None] = 'f79840d8a11e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Create a temporary mapping of duplicate tags to canonical tags
    # Find the canonical (oldest) tag for each (name, organization_id) pair
    op.execute("""
        CREATE TEMP TABLE tag_mapping AS
        SELECT 
            t1.id as duplicate_id,
            t2.id as canonical_id
        FROM tag t1
        INNER JOIN (
            SELECT DISTINCT ON (name, organization_id) id, name, organization_id
            FROM tag
            ORDER BY name, organization_id, created_at ASC
        ) t2 ON t1.name = t2.name AND t1.organization_id = t2.organization_id
        WHERE t1.id != t2.id;
    """)
    
    # Step 2: Update tagged_item entries to use canonical tags
    op.execute("""
        UPDATE tagged_item
        SET tag_id = tm.canonical_id
        FROM tag_mapping tm
        WHERE tagged_item.tag_id = tm.duplicate_id;
    """)
    
    # Step 3: Remove duplicate tagged_item entries (after consolidation, there might be duplicates)
    op.execute("""
        DELETE FROM tagged_item
        WHERE id NOT IN (
            SELECT DISTINCT ON (tag_id, entity_id, entity_type, organization_id) id
            FROM tagged_item
            ORDER BY tag_id, entity_id, entity_type, organization_id, created_at ASC
        );
    """)
    
    # Step 4: Now delete duplicate tags (they're no longer referenced)
    op.execute("""
        DELETE FROM tag
        WHERE id IN (SELECT duplicate_id FROM tag_mapping);
    """)
    
    # Step 5: Drop the temporary table
    op.execute("DROP TABLE tag_mapping;")
    
    # Step 6: Add unique constraint on tag (name, organization_id)
    # This ensures each tag name is unique within an organization
    op.create_unique_constraint(
        'uq_tag_name_organization',
        'tag',
        ['name', 'organization_id']
    )
    
    # Step 7: Add unique constraint on tagged_item (tag_id, entity_id, entity_type, organization_id)
    # This ensures a tag can only be assigned once to a specific entity
    op.create_unique_constraint(
        'uq_tagged_item_assignment',
        'tagged_item',
        ['tag_id', 'entity_id', 'entity_type', 'organization_id']
    )


def downgrade() -> None:
    # Drop the unique constraints
    op.drop_constraint('uq_tagged_item_assignment', 'tagged_item', type_='unique')
    op.drop_constraint('uq_tag_name_organization', 'tag', type_='unique')
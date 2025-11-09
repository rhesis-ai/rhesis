from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis

# Import our simple template loader
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = '6fe8376f15b7'
down_revision: Union[str, None] = '04779f916a43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add TestSetType entries to type_lookup table
    test_set_type_values = """
        ('TestSetType', 'Single-Turn', 'Test set containing only single-turn tests'),
        ('TestSetType', 'Multi-Turn', 'Test set containing only multi-turn tests'),
        ('TestSetType', 'Mixed', 'Test set containing both single-turn and multi-turn tests')
    """.strip()
    op.execute(load_type_lookup_template(test_set_type_values))
    
    # Step 2: Add test_set_type_id column to test_set table
    op.add_column(
        "test_set", 
        sa.Column("test_set_type_id", rhesis.backend.app.models.guid.GUID(), nullable=True)
    )
    op.create_foreign_key("fk_test_set_test_set_type_id", "test_set", "type_lookup", ["test_set_type_id"], ["id"])
    
    # Step 3: Set default test_set_type_id for existing test sets to 'Single-Turn'
    op.execute("""
        UPDATE test_set 
        SET test_set_type_id = (
            SELECT id FROM type_lookup 
            WHERE type_name = 'TestSetType' 
            AND type_value = 'Single-Turn' 
            AND organization_id = test_set.organization_id
        )
        WHERE test_set_type_id IS NULL
    """)


def downgrade() -> None:
    # Step 1: Drop the foreign key constraint and column
    # First, find and drop any foreign key constraint on test_set_type_id
    op.execute("""
        DO $$ 
        DECLARE 
            constraint_name text;
        BEGIN
            SELECT tc.constraint_name INTO constraint_name
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_name='test_set'
            AND kcu.column_name = 'test_set_type_id'
            LIMIT 1;
            
            IF constraint_name IS NOT NULL THEN
                EXECUTE 'ALTER TABLE test_set DROP CONSTRAINT ' || constraint_name;
            END IF;
        END $$;
    """)
    
    op.drop_column("test_set", "test_set_type_id")
    
    # Step 2: Remove TestSetType entries from type_lookup table
    test_set_type_values = "'Single-Turn', 'Multi-Turn', 'Mixed'"
    op.execute(load_cleanup_type_lookup_template("TestSetType", test_set_type_values))
"""Add Error status for test results

This migration adds the 'Error' status to all organizations for TestResult entities.
This status is used when a test execution completes but has no metrics to evaluate.

Revision ID: 416d3e2c6f1f
Revises: 415c0d01df0e
Create Date: 2025-10-28 23:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence


# revision identifiers, used by Alembic.
revision: str = '416d3e2c6f1f'
down_revision: Union[str, None] = '415c0d01df0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add 'Error' status for TestResult entity type to all organizations.
    """
    connection = op.get_bind()
    
    print("Adding 'Error' status for TestResult entity type to all organizations...")
    
    # Get the EntityType for TestResult
    result = connection.execute(sa.text("""
        SELECT id, organization_id 
        FROM type_lookup 
        WHERE type_name = 'EntityType' AND type_value = 'TestResult'
    """))
    
    entity_types = result.fetchall()
    if not entity_types:
        print("⚠️  No TestResult EntityType found")
        return
    
    # Insert Error status for each organization that has TestResult entity type
    inserted_count = 0
    for entity_type in entity_types:
        entity_type_id = entity_type[0]
        organization_id = entity_type[1]
        
        # Check if Error status already exists
        check_result = connection.execute(sa.text("""
            SELECT COUNT(*) 
            FROM status 
            WHERE name = 'Error' 
            AND entity_type_id = :entity_type_id 
            AND organization_id = :organization_id
        """), {"entity_type_id": entity_type_id, "organization_id": organization_id})
        
        if check_result.scalar() == 0:
            # Insert Error status
            connection.execute(sa.text("""
                INSERT INTO status (name, description, entity_type_id, organization_id, created_at, updated_at)
                VALUES ('Error', 'Test execution error (no metrics to evaluate)', :entity_type_id, :organization_id, NOW(), NOW())
            """), {"entity_type_id": entity_type_id, "organization_id": organization_id})
            inserted_count += 1
    
    print(f"✅ Added 'Error' status to {inserted_count} organizations")


def downgrade() -> None:
    """
    Remove 'Error' status for TestResult entity type.
    """
    connection = op.get_bind()
    
    print("Removing 'Error' status for TestResult entity type...")
    
    # Delete Error status for TestResult entity type
    result = connection.execute(sa.text("""
        DELETE FROM status 
        WHERE name = 'Error' 
        AND entity_type_id IN (
            SELECT id FROM type_lookup 
            WHERE type_name = 'EntityType' AND type_value = 'TestResult'
        )
    """))
    
    deleted_count = result.rowcount
    print(f"✅ Removed 'Error' status from {deleted_count} records")


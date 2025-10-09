from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence



# revision identifiers, used by Alembic.
revision: str = '4e087893c30f'
down_revision: Union[str, None] = 'da9164715ec2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create a PostgreSQL function to anonymize user data for GDPR compliance.
    
    This function converts users into "ghost users" by anonymizing all personal data
    while keeping the user record intact to preserve audit trails and foreign key relationships.
    """
    
    # Create the anonymization function
    op.execute("""
        CREATE OR REPLACE FUNCTION gdpr_anonymize_user(user_uuid UUID)
        RETURNS void AS $$
        BEGIN
            -- Update user record with anonymized data
            UPDATE "user"
            SET 
                -- Anonymize name fields
                given_name = 'Previous',
                family_name = 'User',
                name = 'Previous User',
                
                -- Anonymize email with a new random UUID (prevents tracing back to original user)
                email = 'deleted_user_' || gen_random_uuid()::text || '@anonymized.local',
                
                -- Remove profile picture
                picture = NULL,
                
                -- Remove Auth0 ID to prevent login
                auth0_id = NULL,
                
                -- Ensure user is inactive and has no organization
                is_active = false,
                organization_id = NULL,
                
                -- Update timestamp
                updated_at = NOW()
            WHERE id = user_uuid;
            
            -- Raise notice for logging
            RAISE NOTICE 'User % has been anonymized for GDPR compliance', user_uuid;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Add comment to document the function
        COMMENT ON FUNCTION gdpr_anonymize_user(UUID) IS 
        'Anonymizes user data for GDPR compliance (right to erasure). Converts user into a ghost user by removing all personal information while preserving the user record for audit trails and foreign key relationships.';
    """)


def downgrade() -> None:
    """Drop the GDPR anonymization function."""
    op.execute("DROP FUNCTION IF EXISTS gdpr_anonymize_user(UUID);")
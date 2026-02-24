from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aef6c47a8faa"
down_revision: Union[str, None] = "41a9355b3991"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create PostgreSQL functions to manage Polyphemus access control.

    This migration creates two functions:
    1. grant_polyphemus_access: Grants access by setting is_verified=true and updating user_settings
    2. revoke_polyphemus_access: Revokes access by setting is_verified=false and updating user_settings
    """

    # Create the grant access function
    op.execute("""
        CREATE OR REPLACE FUNCTION grant_polyphemus_access(user_uuid UUID)
        RETURNS void AS $$
        DECLARE
            current_settings JSONB;
        BEGIN
            -- Get current user_settings
            SELECT user_settings INTO current_settings
            FROM "user"
            WHERE id = user_uuid;
            
            -- Update user record with verified status
            UPDATE "user"
            SET 
                -- Grant verification
                is_verified = true,
                
                -- Update user_settings with granted timestamp
                user_settings = jsonb_set(
                    COALESCE(current_settings, '{}'::jsonb),
                    '{polyphemus_access,granted_at}',
                    to_jsonb(NOW()),
                    true
                ),
                
                -- Update timestamp
                updated_at = NOW()
            WHERE id = user_uuid;
            
            -- Raise notice for logging
            RAISE NOTICE 'Polyphemus access granted to user %', user_uuid;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Add comment to document the function
        COMMENT ON FUNCTION grant_polyphemus_access(UUID) IS 
        'Grants Polyphemus access to a user by setting is_verified=true and recording the granted_at timestamp in user_settings.polyphemus_access. Should only be called after reviewing user access request.';
    """)

    # Create the revoke access function
    op.execute("""
        CREATE OR REPLACE FUNCTION revoke_polyphemus_access(user_uuid UUID)
        RETURNS void AS $$
        DECLARE
            current_settings JSONB;
            gen_model_id UUID;
            eval_model_id UUID;
            gen_is_polyphemus BOOLEAN := false;
            eval_is_polyphemus BOOLEAN := false;
            updated_settings JSONB;
        BEGIN
            -- Get current user_settings
            SELECT user_settings INTO current_settings
            FROM "user"
            WHERE id = user_uuid;
            
            -- Extract model IDs from settings if they exist
            gen_model_id := (current_settings->'models'->'generation'->>'model_id')::UUID;
            eval_model_id := (current_settings->'models'->'evaluation'->>'model_id')::UUID;
            
            -- Check if generation model is Polyphemus
            IF gen_model_id IS NOT NULL THEN
                SELECT EXISTS(
                    SELECT 1 FROM model m
                    JOIN type_lookup tl ON m.provider_type_id = tl.id
                    WHERE m.id = gen_model_id 
                    AND tl.type_value = 'polyphemus'
                ) INTO gen_is_polyphemus;
            END IF;
            
            -- Check if evaluation model is Polyphemus
            IF eval_model_id IS NOT NULL THEN
                SELECT EXISTS(
                    SELECT 1 FROM model m
                    JOIN type_lookup tl ON m.provider_type_id = tl.id
                    WHERE m.id = eval_model_id 
                    AND tl.type_value = 'polyphemus'
                ) INTO eval_is_polyphemus;
            END IF;
            
            -- Start with current settings
            updated_settings := COALESCE(current_settings, '{}'::jsonb);
            
            -- Set revoked timestamp
            updated_settings := jsonb_set(
                updated_settings,
                '{polyphemus_access,revoked_at}',
                to_jsonb(NOW()),
                true
            );
            
            -- Clear generation model if it's Polyphemus
            IF gen_is_polyphemus THEN
                updated_settings := jsonb_set(
                    updated_settings,
                    '{models,generation,model_id}',
                    'null'::jsonb,
                    true
                );
                RAISE NOTICE 'Cleared Polyphemus generation model for user %', user_uuid;
            END IF;
            
            -- Clear evaluation model if it's Polyphemus
            IF eval_is_polyphemus THEN
                updated_settings := jsonb_set(
                    updated_settings,
                    '{models,evaluation,model_id}',
                    'null'::jsonb,
                    true
                );
                RAISE NOTICE 'Cleared Polyphemus evaluation model for user %', user_uuid;
            END IF;
            
            -- Update user record with revoked status
            UPDATE "user"
            SET 
                -- Revoke verification
                is_verified = false,
                
                -- Update user_settings with revoked timestamp and cleared models
                user_settings = updated_settings,
                
                -- Update timestamp
                updated_at = NOW()
            WHERE id = user_uuid;
            
            -- Raise notice for logging
            RAISE NOTICE 'Polyphemus access revoked for user %', user_uuid;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Add comment to document the function
        COMMENT ON FUNCTION revoke_polyphemus_access(UUID) IS 
        'Revokes Polyphemus access from a user by setting is_verified=false, recording the revoked_at timestamp, and clearing any Polyphemus models from generation/evaluation settings.';
    """)


def downgrade() -> None:
    """Drop the Polyphemus access control functions."""
    op.execute("DROP FUNCTION IF EXISTS grant_polyphemus_access(UUID);")
    op.execute("DROP FUNCTION IF EXISTS revoke_polyphemus_access(UUID);")

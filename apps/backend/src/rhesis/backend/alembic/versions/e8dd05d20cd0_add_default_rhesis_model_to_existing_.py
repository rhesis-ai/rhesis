"""add_default_rhesis_model_to_existing_orgs

This migration adds the default Rhesis model to all existing organizations.
For new organizations, the model is created during onboarding via load_initial_data.

Revision ID: e8dd05d20cd0
Revises: 10c4e8124417
Create Date: 2025-10-26 18:58:31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from typing import Union, Sequence
import uuid

# Import models and utilities
from rhesis.backend.app import models
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_entity,
    get_or_create_type_lookup,
    get_or_create_status,
)
from rhesis.backend.app.constants import DEFAULT_MODEL_NAME, EntityType

# revision identifiers, used by Alembic.
revision: str = 'e8dd05d20cd0'
down_revision: Union[str, None] = '10c4e8124417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add the default Rhesis model to all existing organizations.
    
    Uses existing utility functions to create models with proper error handling
    and consistency with the load_initial_data function.
    """
    bind = op.get_bind()
    session = Session(bind=bind)
    
    try:
        # Get all organizations (including those that haven't completed onboarding)
        organizations = session.query(models.Organization).all()
        
        print(f"\n📦 Creating default Rhesis model for {len(organizations)} organization(s)...")
        created_count = 0
        skipped_count = 0
        
        for org in organizations:
            organization_id = str(org.id)
            # Use owner_id or fall back to user_id
            user_id = str(org.owner_id or org.user_id)
            
            if not user_id:
                print(f"  ⚠ Skipping org {organization_id}: No owner or user")
                skipped_count += 1
                continue
            
            # Check if a protected Rhesis model already exists
            existing_model = (
                session.query(models.Model)
                .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
                .filter(
                    models.Model.organization_id == org.id,
                    models.TypeLookup.type_value == 'rhesis',
                    models.Model.is_protected == True
                )
                .first()
            )
            
            if existing_model:
                print(f"  ⏭ Skipping org {organization_id}: Rhesis model already exists")
                skipped_count += 1
                continue
            
            try:
                # Get or create the rhesis provider type
                rhesis_provider_type = get_or_create_type_lookup(
                    db=session,
                    type_name="ProviderType",
                    type_value="rhesis",
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False
                )
                
                # Get or create the Available status for Model entity type
                available_status = get_or_create_status(
                    db=session,
                    name="Available",
                    entity_type=EntityType.MODEL,
                    description="Model is ready and can be used",
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False
                )
                
                # Create the default Rhesis model
                default_model_data = {
                    "name": "Rhesis Default",
                    "model_name": DEFAULT_MODEL_NAME,
                    "description": "Default Rhesis-hosted model. No API key required.",
                    "icon": "rhesis",
                    "provider_type_id": rhesis_provider_type.id,
                    "status_id": available_status.id,
                    "key": "",
                    "endpoint": None,
                    "is_protected": True,
                    "user_id": uuid.UUID(user_id),
                    "owner_id": uuid.UUID(user_id),
                }
                
                get_or_create_entity(
                    db=session,
                    model=models.Model,
                    entity_data=default_model_data,
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False
                )
                
                created_count += 1
                print(f"  ✓ Created Rhesis model for org {organization_id}")
                
            except Exception as e:
                print(f"  ✗ Error creating model for org {organization_id}: {e}")
                skipped_count += 1
                continue
        
        # Commit all changes
        session.commit()
        print(f"\n✅ Migration complete: {created_count} created, {skipped_count} skipped\n")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {e}\n")
        raise
    finally:
        session.close()


def downgrade() -> None:
    """
    Remove the default Rhesis models that were created by this migration.
    
    WARNING: This will only remove protected Rhesis models, not any user-created Rhesis models.
    """
    bind = op.get_bind()
    session = Session(bind=bind)
    
    try:
        # Find protected Rhesis models to delete
        models_to_delete = (
            session.query(models.Model)
            .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
            .filter(
                models.Model.is_protected == True,
                models.Model.name == 'Rhesis Default',
                models.TypeLookup.type_value == 'rhesis'
            )
            .all()
        )
        
        deleted_count = len(models_to_delete)
        
        # Delete each model individually
        for model in models_to_delete:
            session.delete(model)
        
        session.commit()
        print(f"\n🗑 Removed {deleted_count} default Rhesis model(s)\n")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Downgrade failed: {e}\n")
        raise
    finally:
        session.close()
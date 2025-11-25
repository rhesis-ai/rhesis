from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.status import Status


def get_or_create_status(
    session: Session,
    status_name: str,
    entity_type: str,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[Status]:
    """
    Get or create a Status object from the database.

    Args:
        session: SQLAlchemy database session
        status_name: Name of the status to look up
        entity_type: Type of entity this status applies to (e.g., "Test", "Task")
        organization_id: Organization ID for filtering (SECURITY CRITICAL)
        user_id: User ID for creating new status entries (required if organization_id is provided)

    Returns:
        The Status object if found or created, None otherwise
    """
    from uuid import UUID

    from rhesis.backend.app.models.type_lookup import TypeLookup

    # First, get or create the TypeLookup for the entity type
    entity_type_query = session.query(TypeLookup).filter(
        TypeLookup.type_name == "EntityType", TypeLookup.type_value == entity_type
    )
    if organization_id:
        entity_type_query = entity_type_query.filter(
            TypeLookup.organization_id == UUID(organization_id)
        )

    entity_type_lookup = entity_type_query.first()
    if not entity_type_lookup:
        # Create the entity type lookup if it doesn't exist
        entity_type_data = {"type_name": "EntityType", "type_value": entity_type}
        if organization_id:
            entity_type_data["organization_id"] = UUID(organization_id)
            if user_id:
                entity_type_data["user_id"] = UUID(user_id)

        entity_type_lookup = TypeLookup(**entity_type_data)
        session.add(entity_type_lookup)
        session.flush()  # Get the ID

    # Now look for the status using the entity_type_id
    query = session.query(Status).filter(
        Status.name == status_name, Status.entity_type_id == entity_type_lookup.id
    )

    if organization_id:
        query = query.filter(Status.organization_id == UUID(organization_id))

    status = query.first()
    if not status:
        # Create new status with organization context
        status_data = {"name": status_name, "entity_type_id": entity_type_lookup.id}
        if organization_id:
            status_data["organization_id"] = UUID(organization_id)
            if user_id:
                status_data["user_id"] = UUID(user_id)

        status = Status(**status_data)
        session.add(status)
        session.flush()  # Flush to get the ID, commit handled by session context manager
    return status

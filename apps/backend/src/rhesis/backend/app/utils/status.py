from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.status import Status


def get_or_create_status(session: Session, status_name: str, entity_type: str, organization_id: str = None) -> Optional[Status]:
    """
    Get or create a Status object from the database based on its name, entity type, and organization.

    Args:
        session: SQLAlchemy database session
        status_name: Name of the status to look up
        entity_type: Type of entity this status applies to
        organization_id: Organization ID for filtering (SECURITY CRITICAL)

    Returns:
        The Status object if found or created, None otherwise
    """
    # Apply organization filtering (SECURITY CRITICAL)
    query = session.query(Status).filter(Status.name == status_name, Status.entity_type == entity_type)
    
    if organization_id:
        from uuid import UUID
        query = query.filter(Status.organization_id == UUID(organization_id))
    
    status = query.first()
    if not status:
        # Create new status with organization context
        status_data = {
            "name": status_name, 
            "entity_type": entity_type
        }
        if organization_id:
            status_data["organization_id"] = UUID(organization_id)
            
        status = Status(**status_data)
        session.add(status)
        session.commit()
    return status

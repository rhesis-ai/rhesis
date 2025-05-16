from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.status import Status


def get_or_create_status(session: Session, status_name: str, entity_type: str) -> Optional[Status]:
    """
    Get or create a Status object from the database based on its name and entity type.

    Args:
        session: SQLAlchemy database session
        status_name: Name of the status to look up
        entity_type: Type of entity this status applies to

    Returns:
        The Status object if found or created, None otherwise
    """
    status = (
        session.query(Status)
        .filter(Status.name == status_name, Status.entity_type == entity_type)
        .first()
    )
    if not status:
        # Create new status
        status = Status(name=status_name, entity_type=entity_type)
        session.add(status)
        session.commit()
    return status

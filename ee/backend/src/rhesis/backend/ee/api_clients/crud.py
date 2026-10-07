"""CRUD operations for :class:`AuthClient` rows."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.ee.api_clients.clients import AuthClient


def create_auth_client(db: Session, **fields) -> AuthClient:
    """Insert an API client and commit.

    Raises ``IntegrityError`` on a duplicate ``client_id`` or name; the session
    is rolled back first, so the caller only has to map it to a response.
    """
    row = AuthClient(**fields)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(row)
    return row

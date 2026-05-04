"""Target factory for endpoint exploration tasks.

Provides ``make_target_factory`` — returns a callable
``(endpoint_id) -> BackendEndpointTarget`` for use with
``ExploreEndpointTool`` in Celery task contexts.

The caller is responsible for managing the DB session lifetime;
the factory closes over an already-open session so that
``BackendEndpointTarget.send_message`` can be called across
multiple conversation turns without reopening the connection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

logger = logging.getLogger(__name__)


def make_target_factory(
    org_id: str,
    user_id: str,
    db: "Session",
) -> Callable[[str], "BackendEndpointTarget"]:
    """Return a factory that creates ``BackendEndpointTarget`` instances.

    Args:
        org_id: Organization UUID string for tenant isolation.
        user_id: User UUID string for tenant isolation.
        db: An open SQLAlchemy session.  The caller must keep this session
            alive for the entire duration of the exploration (i.e. until
            all ``send_message`` calls on the returned targets complete).

    Returns:
        A callable ``(endpoint_id: str) -> BackendEndpointTarget``.
    """
    from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

    def factory(endpoint_id: str) -> BackendEndpointTarget:
        return BackendEndpointTarget(
            db=db,
            endpoint_id=endpoint_id,
            organization_id=org_id,
            user_id=str(user_id),
        )

    return factory

"""CRUD operations for endpoints.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the single-item endpoint CRUD functions, and new code goes into modules like this one
instead of growing the monolith further -- see ``apps/backend/AGENTS.md``'s crud-layout rule.
"""

import uuid
from typing import Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.crud_utils import bulk_delete_by_ids


def bulk_delete_endpoints(
    db: Session,
    endpoint_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """Soft delete multiple endpoints in one transaction.

    No owner-only rule on endpoint delete, so this is a direct wrapper around
    the generic bulk helper.
    """
    return bulk_delete_by_ids(
        db,
        models.Endpoint,
        endpoint_ids,
        organization_id=organization_id,
        user_id=user_id,
    )

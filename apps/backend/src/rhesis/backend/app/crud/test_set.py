"""CRUD operations for test sets.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
most test-set functions, and new code goes into modules like this one instead of growing
the monolith further -- see ``apps/backend/AGENTS.md``'s crud-layout rule.
"""

import uuid
from typing import Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.crud_utils import bulk_delete_by_ids


def bulk_delete_test_sets(
    db: Session,
    test_set_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """
    Soft delete multiple test sets in one transaction.

    TestSet's ``visibility`` column is the only ownership gate on delete --
    unlike TestRun, there's no owner-only ":own" rule layered on top -- so
    this is a direct wrapper around the generic bulk helper.
    """
    return bulk_delete_by_ids(
        db,
        models.TestSet,
        test_set_ids,
        organization_id=organization_id,
        user_id=user_id,
    )

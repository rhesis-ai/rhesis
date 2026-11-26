"""The id of a TestResult status by name, cached per organization.

Every stored test result and evaluated trace names one of a few statuses ("Pass",
"Fail", "Error"), so the lookup is cached instead of read per row.
"""

from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.status import find_status_id
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.app.utils.ttl_cache import TTLCache

# Status rows are created once per organization and not renamed.
_TTL_SECONDS = 300

_status_ids = TTLCache(lambda: _TTL_SECONDS)


class _NotCreatedYet(Exception):
    pass


def test_result_status_id(db: Session, organization_id: str, name: str) -> Optional[str]:
    """The id of the organization's TestResult status *name*, created if missing.

    Only a status that already existed is cached: one created here is part of the
    caller's transaction, which may still roll back.
    """

    def load() -> str:
        status_id = find_status_id(db, organization_id, name, "TestResult")
        if status_id is None:
            raise _NotCreatedYet()
        return str(status_id)

    try:
        return _status_ids.get_or_load((str(organization_id), name), load)
    except _NotCreatedYet:
        status = get_or_create_status(db, name, "TestResult", organization_id=organization_id)
        return str(status.id) if status else None

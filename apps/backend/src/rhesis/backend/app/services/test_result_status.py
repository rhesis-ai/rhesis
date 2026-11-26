"""The id of a TestResult status by name, cached per organization.

Every stored test result and evaluated trace names one of a few statuses ("Pass",
"Fail", "Error"), so the lookup is cached instead of read per row.
"""

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.status import find_status_id
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.app.utils.ttl_cache import TTLCache

# Status rows are created once per organization and not renamed.
_TTL_SECONDS = 300

_status_ids = TTLCache(lambda: _TTL_SECONDS)


class _NotCommittedYet(Exception):
    pass


# Session.info key: statuses this session created, which its transaction may still roll back.
_CREATED_HERE = "test_result_status_ids_created"


def test_result_status_id(db: Session, organization_id: str, name: str) -> str:
    """The id of the organization's TestResult status *name*, created if missing.

    Only a status committed before this session created anything is cached: one created
    here, or found again later in the same session, is part of a transaction that may
    still roll back.

    Raises:
        ValueError: the status could not be found or created.
    """
    created = db.info.setdefault(_CREATED_HERE, set())

    def load() -> str:
        status_id = find_status_id(db, organization_id, name, "TestResult")
        if status_id is None or str(status_id) in created:
            raise _NotCommittedYet()
        return str(status_id)

    try:
        return _status_ids.get_or_load((str(organization_id), name), load)
    except _NotCommittedYet:
        status = get_or_create_status(db, name, "TestResult", organization_id=organization_id)
        if status is None:
            raise ValueError(f"No TestResult status {name!r} for organization {organization_id}")
        created.add(str(status.id))
        return str(status.id)

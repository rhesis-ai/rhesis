"""How a table's writes show up in the audit log.

Every model is audited by default, so a new one cannot silently escape. A model
opts out or classifies columns with ``__audit__``; a many-to-many table declares
its owner in ``Table(..., info={"audit": AuditLink(...)})``.

``tests/backend/models/test_audit_declarations.py`` fails when an audited model
has a ``Text`` or JSON column that is not classified, because that is where
customer content and secrets hide.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AuditPolicy:
    """Column handling for an audited model.

    ``EncryptedString`` columns are always ``secret``. Anything not named here
    records its before and after values.
    """

    audited: bool = True
    # The capability resource, when it is not the table name.
    resource: Optional[str] = None
    # Customer content: values kept only when the org opts in, stored encrypted.
    content: tuple[str, ...] = ()
    # Recorded as "changed", never with values.
    secret: tuple[str, ...] = ()
    # Free text or JSON whose values are fine to record.
    plain: tuple[str, ...] = ()
    # Bookkeeping the system touches on its own, like a last-used timestamp.
    ignore: tuple[str, ...] = ()
    # The column that names the row's organization.
    org_column: str = "organization_id"
    # The column snapshotted as the resource's name.
    label: Optional[str] = None


NOT_AUDITED = AuditPolicy(audited=False)


@dataclass(frozen=True)
class AuditLink:
    """A link row, recorded as a change on the row that owns it.

    Adding test X to test set Y is ``test_set.updated`` with ``tests`` gaining X:
    the change's ``after`` lists added ids and ``before`` removed ones.
    """

    owner: Optional[str]  # owner resource; None when ``owner_type`` names its class
    owner_id: str
    field: str
    linked_id: str
    owner_type: Optional[str] = None

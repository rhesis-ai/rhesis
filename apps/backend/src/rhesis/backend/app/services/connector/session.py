"""Session plumbing for the SDK connector's inbound message path.

Inbound messages arrive faster than anything else on this loop, and
``get_db_with_tenant_variables`` is synchronous: a pool checkout plus a GUC
round trip, blocking the loop until it returns. Most message types never touch
the database, so callers pass a factory and a session is opened only where a
handler actually asks for one.
"""

from contextlib import AbstractContextManager, contextmanager
from typing import Callable, Generator, Optional

from sqlalchemy.orm import Session

#: Opens a tenant-scoped session on demand. The router builds one per message
#: from ``get_db_with_tenant_variables``; tests supply their own.
DbSessionFactory = Callable[[], AbstractContextManager[Session]]


@contextmanager
def resolve_session(
    db: Optional[Session] = None,
    db_factory: Optional[DbSessionFactory] = None,
) -> Generator[Optional[Session], None, None]:
    """Yield whichever session the caller supplied, opening one only if asked.

    An already-open ``db`` wins, so callers that own a session keep owning its
    lifetime. With neither argument this yields ``None``, which every handler
    already reads as "skip the database work".
    """
    if db is not None:
        yield db
    elif db_factory is not None:
        with db_factory() as session:
            yield session
    else:
        yield None

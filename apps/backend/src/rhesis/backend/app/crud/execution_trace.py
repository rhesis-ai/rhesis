"""CRUD operations for execution traces reported by the SDK connector."""

from sqlalchemy.orm import Session

from rhesis.backend.app.models.execution_trace import ExecutionTrace


def create_execution_trace(db: Session, **fields) -> ExecutionTrace:
    """Insert an execution trace and flush, so its server-generated id is set.

    Flushes rather than commits: the caller's tenant session owns the commit.
    """
    record = ExecutionTrace(**fields)
    db.add(record)
    db.flush()
    return record

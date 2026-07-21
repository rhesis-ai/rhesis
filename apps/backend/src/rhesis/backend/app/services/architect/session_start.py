"""Start an Architect turn from REST (contextual handoffs).

Mirrors the WebSocket ``handle_architect_message`` path so Insights and other
entry points reuse the same Celery runner and Redis pub/sub channel.
"""

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas


def start_session_with_message(
    *,
    db: Session,
    db_session: models.ArchitectSession,
    user_message: str,
    organization_id: str,
    user_id: str,
) -> None:
    """Persist the first user turn and dispatch the Architect Celery task.

    Commits before enqueue so the worker can see the session and user message
    (same ordering as the WebSocket handler, which exits its DB context before
    ``apply_async``).
    """
    session_id = str(db_session.id)
    project_id = str(db_session.project_id) if db_session.project_id else None

    crud.create_architect_message(
        db=db,
        message=schemas.ArchitectMessageCreate(
            session_id=db_session.id,
            role="user",
            content=user_message,
            project_id=project_id,
        ),
        organization_id=organization_id,
        user_id=user_id,
    )

    # Flush alone is not enough — create_item only flushes; the request
    # context manager commits on exit. Enqueue only after the rows are durable.
    db.commit()

    from rhesis.backend.tasks.architect import architect_chat_task

    task_headers = {
        "organization_id": organization_id,
        "user_id": user_id,
    }
    if project_id:
        task_headers["project_id"] = project_id

    architect_chat_task.apply_async(
        kwargs={
            "session_id": session_id,
            "user_message": user_message,
        },
        headers=task_headers,
    )

"""SQLAlchemy session hooks to enqueue embedding generation for embeddable entities."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from rhesis.backend.app.models.mixins import EmbeddableMixin
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.embedding.services import EmbeddingService
from rhesis.backend.app.database import get_db
logger = logging.getLogger(__name__)

_SESSION_EMBEDDABLE_KEY = "embeddable_objects"


@event.listens_for(Session, "before_commit")
def track_embeddable_objects(session: Session) -> None:
    """Collect embeddable instances created or with updated searchable text; read after commit."""
    pending: list[Any] = []

    for obj in session.new:
        if isinstance(obj, EmbeddableMixin):
            pending.append(obj)

    for obj in session.dirty:
        if isinstance(obj, EmbeddableMixin) and obj.searchable_text_changed():
            pending.append(obj)

    if pending:
        session.info[_SESSION_EMBEDDABLE_KEY] = pending


@event.listens_for(Session, "after_commit")
def generate_embeddings_after_commit(session: Session) -> None:
    """Enqueue or run embedding generation after the transaction is visible to workers."""
    embeddable_objects = session.info.pop(_SESSION_EMBEDDABLE_KEY, None)
    if not embeddable_objects:
        return

    user_ids = {obj.user_id for obj in embeddable_objects if getattr(obj, "user_id", None)}

    # Query in a separate session to avoid reopening a transaction on the caller's session
    with get_db() as lookup_session:
        users_by_id = {
            u.id: u for u in lookup_session.query(User).filter(User.id.in_(user_ids)).all()
        }

    embedding_service = EmbeddingService(session)
    for obj in embeddable_objects:
        uid = getattr(obj, "user_id", None)
        current_user = users_by_id.get(uid) if uid is not None else None
        if not current_user:
            logger.warning(
                "Skipping embedding for %s id=%s: user not found (user_id=%s)",
                type(obj).__name__,
                getattr(obj, "id", None),
                uid,
            )
            continue
        embedding_service.enqueue_embedding(obj, current_user=current_user)

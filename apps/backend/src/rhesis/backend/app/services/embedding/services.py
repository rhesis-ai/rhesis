"""Embedding generation service with async/sync orchestration."""

import logging
import time
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.async_service import AsyncService
from rhesis.backend.app.utils.user_model_utils import model_setup_problem
from rhesis.backend.jobs import launch_job
from rhesis.backend.jobs.embedding import generate_embedding_task

logger = logging.getLogger(__name__)

#: When each org was last warned about, so a missing model is one warning an hour
#: rather than one per saved entity.
_WARN_EVERY_SECONDS = 3600
_last_warned: dict[str, float] = {}


def _skip_embedding(organization_id: str, reason: str) -> None:
    now = time.monotonic()
    if now - _last_warned.get(organization_id, -_WARN_EVERY_SECONDS) < _WARN_EVERY_SECONDS:
        logger.debug("Skipping embedding for org_id=%s: %s", organization_id, reason)
        return
    # Drop expired entries so the map can't grow without bound.
    for org_id, at in list(_last_warned.items()):
        if now - at >= _WARN_EVERY_SECONDS:
            del _last_warned[org_id]
    _last_warned[organization_id] = now
    logger.warning(
        "Skipping embeddings for org_id=%s until a usable embedding model is set up "
        "(logged at most hourly): %s",
        organization_id,
        reason,
    )


class EmbeddingService(AsyncService):
    """Service for orchestrating embedding generation tasks."""

    def __init__(self, db: Session):
        super().__init__()
        self.db = db

    def _execute_sync(self, model_id: str, **kwargs):
        from rhesis.backend.app.services.embedding.generator import EmbeddingGenerator

        entity_type = kwargs["entity_type"]
        entity_id = kwargs["entity_id"]
        searchable_text = kwargs["searchable_text"]
        user_id = kwargs["user_id"]
        organization_id = kwargs["organization_id"]

        generator = EmbeddingGenerator(self.db)
        generator.generate(
            entity_id=str(entity_id),
            entity_type=entity_type,
            organization_id=str(organization_id),
            user_id=str(user_id),
            model_id=str(model_id),
            searchable_text=searchable_text,
            entity=None,
        )

    def _enqueue_async(self, model_id: str, **kwargs):
        entity_id = str(kwargs["entity_id"])
        entity_type = kwargs["entity_type"]
        searchable_text = kwargs["searchable_text"]
        user_id = str(kwargs["user_id"])
        organization_id = str(kwargs["organization_id"])

        # entity_id/entity_type go to the task positionally: launch_job has keyword
        # parameters of the same names (the job-row link) and would swallow them.
        launch_job(
            generate_embedding_task,
            entity_id,
            entity_type,
            model_id=str(model_id),
            searchable_text=searchable_text,
            current_user=SimpleNamespace(id=user_id, organization_id=organization_id),
            db=self.db,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def resolve_model_id(self, user_id: str, model_id: str | None = None) -> str:
        """Resolve embedding model ID from explicit value or user settings."""

        # 1. Use explicit model_id if provided
        if model_id:
            return str(model_id)

        # 2. Query user settings
        user = self.db.query(User).filter(User.id == user_id).first()

        if user and user.settings and user.settings.models and user.settings.models.embedding:
            resolved_model_id = user.settings.models.embedding.model_id
            if resolved_model_id:
                return str(resolved_model_id)

        raise ValueError(f"No embedding model found for user {user_id}")

    def _usable_model_id(self, user_id: str, model_id: str | None) -> tuple[str | None, str]:
        """The embedding model to use, or ``(None, reason)``. Checked before queuing since
        this runs on every entity save and would otherwise fail on each one."""
        try:
            resolved = self.resolve_model_id(user_id, model_id)
        except ValueError:
            return None, "no default embedding model is set"
        # Identity-map hit after resolve_model_id's query, so no second read.
        user = self.db.get(User, UUID(user_id))
        problem = model_setup_problem(self.db, user, "embedding", resolved) if user else None
        return (None, problem.log_message) if problem else (resolved, "")

    def enqueue_embedding(
        self,
        *,
        entity_type: str,
        entity_id: str,
        searchable_text: str,
        user_id: str,
        organization_id: str,
        model_id: str | None = None,
    ) -> bool:
        """Enqueue embedding generation using entity identity and precomputed searchable text."""
        try:
            resolved_model_id, reason = self._usable_model_id(str(user_id), model_id)
            if resolved_model_id is None:
                _skip_embedding(str(organization_id), reason)
                return False
            was_async, _ = self.execute_with_fallback(
                resolved_model_id,
                entity_type=entity_type,
                entity_id=entity_id,
                searchable_text=searchable_text,
                user_id=str(user_id),
                organization_id=str(organization_id),
            )
            return was_async
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return False

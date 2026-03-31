"""Embedding generation service with async/sync orchestration."""

import logging

from sqlalchemy.orm import Session

from rhesis.backend.app.models.mixins import EmbeddableMixin
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.async_service import AsyncService
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.embedding import generate_embedding_task

logger = logging.getLogger(__name__)


class EmbeddingService(AsyncService):
    """Service for orchestrating embedding generation tasks."""

    def __init__(self, db: Session):
        super().__init__()
        self.db = db

    def _execute_sync(self, entity: EmbeddableMixin, model_id: str, current_user: User):
        from rhesis.backend.app.services.embedding.generator import EmbeddingGenerator

        generator = EmbeddingGenerator(self.db)
        generator.generate(
            entity_id=str(entity.id),
            entity_type=entity.__class__.__name__,
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            model_id=str(model_id),
            entity=entity,
        )

    def _enqueue_async(self, entity_id: str, entity_type: str, model_id: str, current_user: User):
        task_launcher(
            generate_embedding_task,
            entity_id=entity_id,
            entity_type=entity_type,
            model_id=model_id,
            current_user=current_user,
        )

    def _resolve_model_id(self, user_id: str, model_id: str = None) -> str:
        """Resolve embedding configuration from user settings or defaults."""

        # 1. Use explicit model_id if provided
        if model_id:
            return model_id

        # 2. Query user settings
        user = self.db.query(User).filter(User.id == user_id).first()

        if user and user.settings and user.settings.models and user.settings.models.embedding:
            resolved_model_id = user.settings.models.embedding.model_id
            if resolved_model_id:
                return resolved_model_id

        raise ValueError(f"No embedding model found for user {user_id}")

    def enqueue_embedding(self, entity: EmbeddableMixin, current_user: User) -> bool:
        """Enqueue embedding generation for an entity."""
        try:
            model_id = self._resolve_model_id(entity.user_id, None)
            was_async, _ = self.execute_with_fallback(
                entity,
                model_id,
                entity_id=entity.id,
                entity_type=entity.__class__.__name__,
                current_user=current_user,
            )
            return was_async
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return False

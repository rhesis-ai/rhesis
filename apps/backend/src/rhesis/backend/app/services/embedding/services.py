"""Embedding generation service with async/sync orchestration."""

import logging
from sqlalchemy.orm import Session

from rhesis.backend.app.services.base import AsyncService
from rhesis.backend.app.models.mixins import EmbeddableMixin

logger = logging.getLogger(__name__)


class EmbeddingService(AsyncService):
    """Service for orchestrating embedding generation tasks."""

    def __init__(self, db: Session):
        super().__init__()
        self.db = db

    def _execute_sync(self, entity: EmbeddableMixin, model_id: str):
        from rhesis.backend.app.services.embedding.generator import EmbeddingGenerator
        generator = EmbeddingGenerator(self.db)
        generator.generate(
            entity_id=str(entity.id),
            entity_type=entity.__class__.__name__,
            organization_id=str(entity.organization_id),
            user_id=str(entity.user_id),
            model_id=str(model_id),
            entity=entity,
        )

    def _enqueue_async(
        self,
        entity_id: str,
        entity_type: str,
        organization_id: str,
        user_id: str,
        model_id: str
    ):
        """Enqueue async embedding generation task."""
        from rhesis.backend.tasks.embedding import generate_embedding_task

        generate_embedding_task.delay(
            entity_id=entity_id,
            entity_type=entity_type,
            organization_id=organization_id,
            user_id=user_id,
            model_id=model_id,
        )


    def _resolve_model_id(self, user_id: str, model_id: str = None) -> str:
        """Resolve embedding configuration from user settings or defaults."""

        # 1. Use explicit model_id if provided
        if model_id:
            return model_id

        # 2. Query user settings
        from rhesis.backend.app.models.user import User
        user = self.db.query(User).filter(User.id == user_id).first()

        if user and user.settings and user.settings.models and user.settings.models.embedding:
            resolved_model_id = user.settings.models.embedding.model_id
            if resolved_model_id:
                return resolved_model_id

        raise ValueError(f"No embedding model found for user {user_id}")


    def enqueue_embedding(self, entity: EmbeddableMixin) -> bool:
        """Enqueue embedding generation for an entity."""
        try:
            model_id = self._resolve_model_id(entity.user_id, None)
            was_async, _ = self.execute_with_fallback(
                entity,
                model_id,
                entity_id=entity.id,
                entity_type=entity.__class__.__name__,
                organization_id=entity.organization_id,
                user_id=entity.user_id
            )
            return was_async
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return False

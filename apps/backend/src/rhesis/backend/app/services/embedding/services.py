"""Embedding generation service with async/sync orchestration."""

import logging
from types import SimpleNamespace

from sqlalchemy.orm import Session

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

        task_launcher(
            generate_embedding_task,
            entity_id=entity_id,
            entity_type=entity_type,
            model_id=str(model_id),
            searchable_text=searchable_text,
            current_user=SimpleNamespace(id=user_id, organization_id=organization_id),
        )

    def _resolve_model_id(self, user_id: str, model_id: str = None) -> str:
        """Resolve embedding configuration from user settings or defaults."""

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
            resolved_model_id = self._resolve_model_id(str(user_id), model_id)
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

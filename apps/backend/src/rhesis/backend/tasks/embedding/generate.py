"""Celery task for embedding generation.

This task generates embeddings for entities in a background worker.
"""

import logging

from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.worker import app

logger = logging.getLogger(__name__)


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.embedding.generate_embedding",
    bind=True,
    display_name="Embedding Generation",
)
def generate_embedding_task(self, entity_id: str, entity_type: str, model_id: str | None = None):
    from rhesis.backend.app.services.embedding.generator import EmbeddingGenerator

    organization_id, user_id = self.get_tenant_context()

    self.log_with_context(
        "info", "Starting embedding generation",
        entity_type=entity_type,
        entity_id=entity_id,
    )

    with self.get_db_session() as db:
        generator = EmbeddingGenerator(db)
        result = generator.generate(
            entity_id=entity_id,
            entity_type=entity_type,
            organization_id=organization_id,
            user_id=user_id,
            model_id=model_id,
        )

    self.log_with_context("info", "Embedding generated successfully", status=result["status"])
    return result

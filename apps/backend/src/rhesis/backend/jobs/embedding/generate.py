"""Celery task for embedding generation.

This task generates embeddings for entities in a background worker.
"""

import logging

from rhesis.backend.celery.core import app
from rhesis.backend.jobs.base import SilentJob

logger = logging.getLogger(__name__)


@app.task(
    base=SilentJob,
    name="rhesis.backend.jobs.embedding.generate_embedding",
    bind=True,
    display_name="Embedding Generation",
)
def generate_embedding_task(
    self,
    entity_id: str,
    entity_type: str,
    model_id: str | None = None,
    searchable_text: str | None = None,
):
    """Run :meth:`~rhesis.backend.app.services.embedding.generator.EmbeddingGenerator.generate`.

    Return value is that method's result dict (``status``, ``embedding_id``). See its
    docstring for ``status`` values, including ``skipped_empty_text`` when text is empty.
    Returns ``skipped_disabled`` without generating anything while embeddings are off.
    """
    from rhesis.backend.app.config.settings import get_application_settings
    from rhesis.backend.app.services.embedding.generator import EmbeddingGenerator

    # Jobs queued before embeddings were switched off.
    if not get_application_settings().embeddings_enabled:
        return {"status": "skipped_disabled", "embedding_id": None}

    organization_id, user_id, _ = self.get_tenant_context()

    self.log_with_context(
        "info",
        "Starting embedding generation",
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
            searchable_text=searchable_text,
        )

    return result

"""Embedding generator for creating embeddings from entities."""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.models.enums import EmbeddingStatus
from rhesis.backend.app.utils.crud_utils import get_item

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embedding for any embeddable entity."""

    def __init__(self, db: Session):
        self.db = db

    def _get_entity(self, entity_id: str, entity_type: str, organization_id: str) -> Any:
        """Get entity from database."""

        try:
            model_class = getattr(models, entity_type)
        except AttributeError:
            raise ValueError(f"Entity type {entity_type} not found")

        entity = get_item(self.db, model_class, entity_id, organization_id)
        if not entity:
            raise ValueError(f"Entity not found: {entity_id}")
        return entity

    def _compute_hash(self, data: str | dict) -> str:
        """Compute SHA-256 hash of input data."""

        # Convert dict to stable string representation
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = data

        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    def _generate_embedding_vector(
        self,
        searchable_text: str,
        provider: str,
        model_name: str,
        api_key: str,
        dimension: int,
    ) -> List[float]:
        """Generate embedding for a searchable text."""
        from rhesis.sdk.models.factory import EmbeddingModelConfig, get_embedding_model

        config = EmbeddingModelConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            dimensions=dimension,
        )
        try:
            embedder = get_embedding_model(config=config, model_type="embedding")
        except ValueError as e:
            raise ValueError(f"Failed to create embedder: {e}")

        try:
            embedding = embedder.generate(searchable_text)
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {e}")

        return embedding

    def generate(
        self,
        entity_id: str,
        entity_type: str,
        organization_id: str,
        user_id: str,
        model_id: str,
        entity: Optional[Any] = None,
        searchable_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate embedding for any embeddable entity.

        Args:
            entity_id: ID of the entity to embed
            entity_type: Type of entity (Test, Source, etc.)
            organization_id: Organization context
            user_id: User context
            model_id: ID of the embedding model to use
            entity: Optional entity object (used when searchable_text is not provided)
            searchable_text: Precomputed searchable text; when set, entity is not loaded for text

        Returns:
            Dictionary with generation result
        """
        if searchable_text is None:
            if not entity:
                entity = self._get_entity(entity_id, entity_type, organization_id)

            if not hasattr(entity, "to_searchable_text"):
                raise ValueError(f"Entity {entity_type} does not support embedding")

            searchable_text = entity.to_searchable_text()

        # Fetch model to get all configuration
        model = crud.get_model(self.db, model_id, organization_id, user_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")

        # Extract model details
        provider = model.provider_type.type_value if model.provider_type else None
        model_name = model.model_name
        dimension = model.dimension

        # Create configuration for this embedding
        config = {
            "provider": provider,
            "model_name": model_name,
            "dimension": dimension,
            "model_id": model_id,
        }

        # Compute hashes for deduplication
        config_hash = self._compute_hash(config)
        text_hash = self._compute_hash(searchable_text)

        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        active_status = get_or_create_status(
            self.db,
            name=EmbeddingStatus.ACTIVE.value,
            entity_type="Embedding",
            organization_id=organization_id,
            user_id=user_id,
        )
        if not active_status:
            raise ValueError("Failed to create or retrieve Active status for Embedding.")

        stale_status = get_or_create_status(
            self.db,
            name=EmbeddingStatus.STALE.value,
            entity_type="Embedding",
            organization_id=organization_id,
            user_id=user_id,
        )
        if not stale_status:
            raise ValueError("Failed to create or retrieve Stale status for Embedding.")

        # Check if embedding already exists (same text/config)
        existing_embedding = crud.get_embedding_by_hash(
            self.db,
            entity_id=entity_id,
            entity_type=entity_type,
            organization_id=organization_id,
            config_hash=config_hash,
            text_hash=text_hash,
            status_id=active_status.id,
        )

        if existing_embedding:
            logger.info(f"Embedding already exists for {entity_type}:{entity_id}")
            return {"status": "success", "embedding_id": str(existing_embedding.id)}

        # Generate the embedding vector
        embedding_vector = self._generate_embedding_vector(
            searchable_text, provider, model_name, model.key, dimension
        )

        # Mark old embeddings as stale (different text/config)
        stale_count = crud.mark_embeddings_stale(
            self.db,
            entity_id=entity_id,
            entity_type=entity_type,
            organization_id=organization_id,
            active_status_id=active_status.id,
            stale_status_id=stale_status.id,
        )

        if stale_count > 0:
            logger.info(f"Marked {stale_count} old embeddings as stale")

        # Create and store the embedding
        embedding_create = schemas.EmbeddingCreate(
            entity_id=entity_id,
            entity_type=entity_type,
            model_id=model_id,
            embedding_config=config,
            config_hash=config_hash,
            searchable_text=searchable_text,
            text_hash=text_hash,
            status_id=active_status.id,
            embedding=embedding_vector,
        )

        from sqlalchemy.exc import IntegrityError

        try:
            with self.db.begin_nested():
                new_embedding = crud.create_embedding(
                    self.db,
                    embedding=embedding_create,
                    organization_id=organization_id,
                    user_id=user_id,
                )
        except IntegrityError:
            # Race condition: another process might have created it
            existing_embedding = crud.get_embedding_by_hash(
                self.db,
                entity_id=entity_id,
                entity_type=entity_type,
                organization_id=organization_id,
                config_hash=config_hash,
                text_hash=text_hash,
                status_id=active_status.id,
            )

            if existing_embedding:
                logger.info(
                    f"Embedding already exists for {entity_type}:{entity_id} "
                    "(found after race condition)"
                )
                return {"status": "success", "embedding_id": str(existing_embedding.id)}
            raise

        logger.info(
            f"Successfully generated embedding for {entity_type}:{entity_id}, dimension={dimension}"
        )

        return {"status": "success", "embedding_id": str(new_embedding.id)}

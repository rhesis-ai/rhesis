"""Embedding generator for creating embeddings from entities."""

import hashlib
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.embedding import EmbeddingStatus
from rhesis.backend.app.models.model import Model
from rhesis.backend.app.utils.crud_utils import get_item
from rhesis.backend.logging import logger


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

        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def _generate_embedding_vector(
        self,
        searchable_text: str,
        provider: str,
        model_name: str,
        api_key: str,
        dimension: int,
        ) -> List[float]:
        """Generate embedding for a searchable text."""
        from rhesis.sdk.models.factory import EmbedderConfig, get_embedder

        config = EmbedderConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            dimensions=dimension,
        )
        try:
            embedder = get_embedder(config=config)
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
    ) -> Dict[str, Any]:
        """
        Generate embedding for any embeddable entity.

        Args:
            entity_id: ID of the entity to embed
            entity_type: Type of entity (Test, Source, etc.)
            organization_id: Organization context
            user_id: User context
            model_id: ID of the embedding model to use
            entity: Optional entity object (avoids re-fetch if provided)

        Returns:
            Dictionary with generation result
        """
        # If entity object provided, use it (sync path -> no extra DB query)
        if not entity:
            entity = self._get_entity(entity_id, entity_type, organization_id)

        if not hasattr(entity, "to_searchable_text"):
            raise ValueError(f"Entity {entity_type} does not support embedding")

        # Fetch model to get all configuration
        model = self.db.query(Model).filter(Model.id == model_id).first()
        if not model:
            raise ValueError(f"Model not found: {model_id}")

        # Extract model details
        provider = model.provider_type.type_value if model.provider_type else None
        model_name = model.model_name
        dimension = model.dimension

        # Get searchable text from entity
        searchable_text = entity.to_searchable_text()

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

        # Check if embedding already exists (same text/config)
        existing_embedding = self.db.query(models.Embedding).filter(
            models.Embedding.entity_id == entity_id,
            models.Embedding.entity_type == entity_type,
            models.Embedding.organization_id == organization_id,
            models.Embedding.config_hash == config_hash,
            models.Embedding.text_hash == text_hash,
            models.Embedding.status == EmbeddingStatus.ACTIVE.value,
        ).first()

        if existing_embedding:
            logger.info(f"Embedding already exists for {entity_type}:{entity_id}")
            return {"status": "success", "embedding_id": str(existing_embedding.id)}

        # Mark old embeddings as stale (different text/config)
        stale_count = (
            self.db.query(models.Embedding)
            .filter(
                models.Embedding.entity_id == entity_id,
                models.Embedding.entity_type == entity_type,
                models.Embedding.organization_id == organization_id,
                models.Embedding.status == EmbeddingStatus.ACTIVE.value,
            )
            .update({"status": EmbeddingStatus.STALE.value})
        )

        if stale_count > 0:
            logger.info(f"Marked {stale_count} old embeddings as stale")

        self.db.flush()

        # Generate the embedding vector
        embedding_vector = self._generate_embedding_vector(
            searchable_text, provider, model_name, model.key, dimension
        )

        # Create and store the embedding
        new_embedding = models.Embedding(
            entity_id=entity_id,
            entity_type=entity_type,
            model_id=model_id,
            embedding_config=config,
            config_hash=config_hash,
            searchable_text=searchable_text,
            text_hash=text_hash,
            organization_id=organization_id,
            user_id=user_id,
            status=EmbeddingStatus.ACTIVE.value,
        )

        # Use the property setter which automatically selects the right column
        new_embedding.embedding = embedding_vector

        self.db.add(new_embedding)
        self.db.commit()
        self.db.refresh(new_embedding)

        logger.info(
            f"Successfully generated embedding for {entity_type}:{entity_id}, "
            f"dimension={dimension}"
        )

        return {"status": "success", "embedding_id": str(new_embedding.id)}

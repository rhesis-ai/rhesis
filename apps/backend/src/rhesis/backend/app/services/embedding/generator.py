"""Embedding generator for creating embeddings from entities."""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.enums import EmbeddingStatus
from rhesis.backend.app.models.model import Model
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

        # Get status IDs
        active_status = (
            self.db.query(models.Status)
            .filter(
                models.Status.name.ilike(EmbeddingStatus.ACTIVE.value),
                models.Status.organization_id == organization_id,
            )
            .first()
        )
        if not active_status:
            active_status = self.db.query(models.Status).first()
            if not active_status:
                raise ValueError("No statuses exist in the database.")

        stale_status = (
            self.db.query(models.Status)
            .filter(
                models.Status.name.ilike(EmbeddingStatus.STALE.value),
                models.Status.organization_id == organization_id,
            )
            .first()
        )
        if not stale_status:
            stale_status = (
                self.db.query(models.Status).filter(models.Status.id != active_status.id).first()
            )
            if not stale_status:
                stale_status = active_status

        # Check if embedding already exists (same text/config)
        existing_embedding = (
            self.db.query(models.Embedding)
            .filter(
                models.Embedding.entity_id == entity_id,
                models.Embedding.entity_type == entity_type,
                models.Embedding.organization_id == organization_id,
                models.Embedding.config_hash == config_hash,
                models.Embedding.text_hash == text_hash,
                models.Embedding.status_id == active_status.id,
            )
            .first()
        )

        if existing_embedding:
            logger.info(f"Embedding already exists for {entity_type}:{entity_id}")
            return {"status": "success", "embedding_id": str(existing_embedding.id)}

        # Generate the embedding vector
        embedding_vector = self._generate_embedding_vector(
            searchable_text, provider, model_name, model.key, dimension
        )

        # Mark old embeddings as stale (different text/config)
        stale_count = (
            self.db.query(models.Embedding)
            .filter(
                models.Embedding.entity_id == entity_id,
                models.Embedding.entity_type == entity_type,
                models.Embedding.organization_id == organization_id,
                models.Embedding.status_id == active_status.id,
            )
            .update({"status_id": stale_status.id})
        )

        if stale_count > 0:
            logger.info(f"Marked {stale_count} old embeddings as stale")

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
            status_id=active_status.id,
        )

        # Use the property setter which automatically selects the right column
        new_embedding.embedding = embedding_vector

        self.db.add(new_embedding)
        self.db.commit()
        self.db.refresh(new_embedding)

        logger.info(
            f"Successfully generated embedding for {entity_type}:{entity_id}, dimension={dimension}"
        )

        return {"status": "success", "embedding_id": str(new_embedding.id)}

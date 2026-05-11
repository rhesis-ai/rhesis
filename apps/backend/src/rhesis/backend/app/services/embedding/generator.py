"""Embedding generator for creating embeddings from entities."""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.models.embedding import EmbeddingConfig
from rhesis.backend.app.models.enums import EmbeddingStatus
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.crud_utils import get_item
from rhesis.backend.app.utils.user_model_utils import get_user_embedding_model
from rhesis.sdk.models.factory import get_model

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

    def _resolve_embedder(self, user_id: str, db_model: models.Model, embedder: Any = None) -> Any:
        """Resolve a runnable embedder instance from user settings when not injected."""
        if embedder is not None:
            return embedder

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        resolved = get_user_embedding_model(self.db, user)
        return (
            get_model(
                resolved,
                model_type="embedding",
                dimensions=db_model.dimension,
            )
            if isinstance(resolved, str)
            else resolved
        )

    def _get_status(self, name: EmbeddingStatus, organization_id: str, user_id: str):
        """Fetch or create embedding status row and fail fast when unavailable."""
        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        status = get_or_create_status(
            self.db,
            name=name.value,
            entity_type="Embedding",
            organization_id=organization_id,
            user_id=user_id,
        )
        if not status:
            raise ValueError(
                f"Failed to create or retrieve {name.value.title()} status for Embedding."
            )
        return status

    @staticmethod
    def _embedding_config_dict(
        db_model: models.Model, model_id: str, dimension: int
    ) -> Dict[str, Any]:
        """JSON blob stored on Embedding rows and used for config_hash / deduplication."""
        return {
            "provider": db_model.provider_type.type_value if db_model.provider_type else None,
            "model_name": db_model.model_name,
            "dimension": dimension,
            "model_id": model_id,
        }

    def _return_if_embedding_exists(
        self,
        *,
        entity_id: str,
        entity_type: str,
        organization_id: str,
        config_hash: str,
        text_hash: str,
        status_id: Any,
        after_race: bool = False,
    ) -> Optional[Dict[str, Any]]:
        existing = crud.get_embedding_by_hash(
            self.db,
            entity_id=entity_id,
            entity_type=entity_type,
            organization_id=organization_id,
            config_hash=config_hash,
            text_hash=text_hash,
            status_id=status_id,
        )
        if existing is None:
            return None
        suffix = " (found after race condition)" if after_race else ""
        logger.info("Embedding already exists for %s:%s%s", entity_type, entity_id, suffix)
        return {"status": "success", "embedding_id": str(existing.id)}

    def generate(
        self,
        entity_id: str,
        entity_type: str,
        organization_id: str,
        user_id: str,
        model_id: str,
        entity: Optional[Any] = None,
        searchable_text: Optional[str] = None,
        embedder: Optional[Any] = None,
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
            embedder: Optional pre-resolved embedder. If missing, it is resolved from user settings.

        Returns:
            Dictionary with generation result
        """
        if searchable_text is None:
            if not entity:
                entity = self._get_entity(entity_id, entity_type, organization_id)

            if not hasattr(entity, "to_searchable_text"):
                raise ValueError(f"Entity {entity_type} does not support embedding")

            searchable_text = entity.to_searchable_text()

        # Model row for persistence / hashing (entity-scoped embedding model)
        db_model = crud.get_model(self.db, model_id=model_id, organization_id=organization_id)
        if not db_model:
            raise ValueError(f"Model not found: {model_id}")
        embedder = self._resolve_embedder(user_id=user_id, db_model=db_model, embedder=embedder)

        text_hash = self._compute_hash(searchable_text)

        active_status = self._get_status(EmbeddingStatus.ACTIVE, organization_id, user_id)
        stale_status = self._get_status(EmbeddingStatus.STALE, organization_id, user_id)

        # When model.dimension is set, cheap dedup before calling the embedder.
        if db_model.dimension is not None:
            preview_config = self._embedding_config_dict(
                db_model, model_id, db_model.dimension
            )
            preview_hash = self._compute_hash(preview_config)
            early = self._return_if_embedding_exists(
                entity_id=entity_id,
                entity_type=entity_type,
                organization_id=organization_id,
                config_hash=preview_hash,
                text_hash=text_hash,
                status_id=active_status.id,
            )
            if early is not None:
                return early

        # Generate the embedding vector
        try:
            embedding_vector = embedder.generate(searchable_text)
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {e}")

        vec_dim = len(embedding_vector)
        if vec_dim not in EmbeddingConfig.SUPPORTED_DIMENSIONS:
            supported = sorted(EmbeddingConfig.SUPPORTED_DIMENSIONS.keys())
            raise ValueError(
                f"Embedding length {vec_dim} is not supported for persistence "
                f"(supported dimensions: {supported})"
            )

        # Persisted config uses actual vector length so storage matches embedding_* columns.
        config = self._embedding_config_dict(db_model, model_id, vec_dim)
        config_hash = self._compute_hash(config)

        duplicate = self._return_if_embedding_exists(
            entity_id=entity_id,
            entity_type=entity_type,
            organization_id=organization_id,
            config_hash=config_hash,
            text_hash=text_hash,
            status_id=active_status.id,
        )
        if duplicate is not None:
            return duplicate

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
            raced = self._return_if_embedding_exists(
                entity_id=entity_id,
                entity_type=entity_type,
                organization_id=organization_id,
                config_hash=config_hash,
                text_hash=text_hash,
                status_id=active_status.id,
                after_race=True,
            )
            if raced is not None:
                return raced
            raise

        logger.info(
            f"Successfully generated embedding for "
            f"{entity_type}:{entity_id}, dimension={vec_dim}"
        )

        return {"status": "success", "embedding_id": str(new_embedding.id)}

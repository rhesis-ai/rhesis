from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel

from rhesis.backend.app.schemas.base import Base


class EmbeddingBase(Base):
    entity_id: UUID4
    entity_type: str
    model_id: UUID4
    embedding_config: Dict[str, Any]
    config_hash: str
    searchable_text: str
    text_hash: str
    weight: float = 1.0
    origin: str = "user"
    status_id: UUID4
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class EmbeddingCreate(EmbeddingBase):
    embedding: Optional[List[float]] = None


class EmbeddingUpdate(EmbeddingBase):
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    model_id: Optional[UUID4] = None
    embedding_config: Optional[Dict[str, Any]] = None
    config_hash: Optional[str] = None
    searchable_text: Optional[str] = None
    text_hash: Optional[str] = None
    weight: Optional[float] = None
    origin: Optional[str] = None
    status_id: Optional[UUID4] = None


class Embedding(EmbeddingBase):
    embedding: Optional[List[float]] = None

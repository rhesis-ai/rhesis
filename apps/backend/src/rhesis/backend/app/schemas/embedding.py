import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import UUID4, Field

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


class Point(Base):
    embedding_id: UUID4
    entity_id: UUID4
    entity_type: str


class ScatterPoint2D(Point):
    cluster_id: str
    x: float  # 2D UMAP coordinates for visualization
    y: float


class Cluster(Base):
    id: str  # "cluster_1", "cluster_2", etc.
    label: str  # A descriptive, LLM-generated label
    size: int  # number of entities in the cluster


class Scatter2DGraph(Base):
    computed_at: datetime.datetime
    clusters: List[Cluster]
    points: List[ScatterPoint2D]


class EmbeddingGraphComputeResponse(Base):
    """Response when a background task to compute the embedding graph has been queued."""

    status: Literal["pending"] = "pending"
    task_id: str


class EmbeddingGraphPendingResponse(Base):
    """Graph is not computed yet or has not been persisted on the test set."""

    status: Literal["pending"] = "pending"


class EmbeddingGraphReadyResponse(Base):
    """Computed 2D embedding graph is available."""

    status: Literal["ready"] = "ready"
    graph: Scatter2DGraph


EmbeddingGraphGetResponse = Annotated[
    Union[EmbeddingGraphPendingResponse, EmbeddingGraphReadyResponse],
    Field(discriminator="status"),
]

from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict

from rhesis.backend.app.schemas.status import Status


class ChunkBase(BaseModel):
    source_id: UUID4
    content: str
    chunk_index: int
    token_count: int
    chunk_metadata: Optional[Dict[str, Any]] = None


class ChunkCreate(ChunkBase):
    pass


class ChunkUpdate(BaseModel):
    content: Optional[str] = None
    chunk_index: Optional[int] = None
    token_count: Optional[int] = None
    chunk_metadata: Optional[Dict[str, Any]] = None


class Chunk(ChunkBase):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    status: Optional[Status] = None

    model_config = ConfigDict(from_attributes=True)

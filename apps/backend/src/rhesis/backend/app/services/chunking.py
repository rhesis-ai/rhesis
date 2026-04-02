import logging

import tiktoken
from fastapi import HTTPException
from pydantic import UUID4
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.utils.status import get_or_create_status
from rhesis.sdk.services.chunker import ChunkingService as SDKChunkingService
from rhesis.sdk.services.chunker import ChunkingStrategy
from rhesis.sdk.services.extractor import ExtractedSource, SourceType

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking text."""

    def __init__(self, db: Session, strategy: ChunkingStrategy):
        self.db = db
        self.strategy = strategy
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def _soft_delete_existing_chunks(self, source_id: UUID4, organization_id: str, user_id: str):
        from datetime import datetime, timezone

        from rhesis.backend.app.models.chunk import Chunk

        self.db.query(Chunk).filter(
            Chunk.source_id == source_id,
            Chunk.organization_id == organization_id,
            Chunk.user_id == user_id,
            Chunk.deleted_at.is_(None),
        ).update({"deleted_at": datetime.now(timezone.utc)})

    def chunk_source(self, source_id: UUID4, organization_id: str, user_id: str):

        source = crud.get_source_with_content(
            db=self.db,
            source_id=source_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        if not source:
            raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

        if not source.content or not source.content.strip():
            logger.warning(f"Skipping chunking for source {source_id} - no content available")
            return []

        # Content already extracted; wrap in ExtractedSource to satisfy SDK interface
        extracted_source = ExtractedSource(
            type=SourceType.DOCUMENT, # TODO: map from source type; does not affect chunking
            name=source.title,
            description=source.description,
            metadata=source.source_metadata or {},
            content=source.content,
        )

        sdk_chunking_service = SDKChunkingService(
            sources=[extracted_source], strategy=self.strategy
        )
        # Generate Chunks via SDK
        sdk_chunks = sdk_chunking_service.chunk()

        if not sdk_chunks:
            logger.warning(f"No chunks generated for source {source_id}")
            return []

        self._soft_delete_existing_chunks(source.id, organization_id, user_id)

        active_status = get_or_create_status(
            self.db, "Active", EntityType.CHUNK, organization_id, user_id
        )

        db_chunks = []
        for i, chunk in enumerate(sdk_chunks):
            token_count = len(self.encoding.encode(chunk.content))
            chunk_create = schemas.ChunkCreate(
                source_id=source.id,
                content=chunk.content,
                chunk_index=i,
                token_count=token_count,
                chunk_metadata=None,
                status_id=active_status.id if active_status else None,
            )
            db_chunk = crud.create_chunk(
                db=self.db, chunk=chunk_create, organization_id=organization_id, user_id=user_id
            )
            db_chunks.append(db_chunk)

        logger.info(f"Created {len(db_chunks)} chunks for source {source_id}")

        return db_chunks

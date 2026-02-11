"""Temporary storage for import sessions.

Two-level cache: in-memory L1 + Redis L2 (optional).
Each import session stores the uploaded file bytes, parsed results,
and validation data keyed by a unique import_id.  TTL-based cleanup
ensures abandoned sessions don't leak memory.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from rhesis.backend.logging import logger

# Default TTL: 30 minutes
DEFAULT_TTL_SECONDS = 30 * 60


@dataclass
class ImportSession:
    """State for a single import session."""

    import_id: str
    file_bytes: bytes
    filename: str
    file_format: str  # json, jsonl, csv, xlsx
    created_at: float = field(default_factory=time.time)

    # Populated after analyze
    headers: List[str] = field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    suggested_mapping: Dict[str, str] = field(default_factory=dict)
    mapping_confidence: float = 0.0

    # Populated after parse
    parsed_rows: List[Dict[str, Any]] = field(default_factory=list)
    row_errors: List[List[Dict[str, str]]] = field(default_factory=list)
    row_warnings: List[List[Dict[str, str]]] = field(default_factory=list)
    validation_summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > DEFAULT_TTL_SECONDS

    @property
    def total_rows(self) -> int:
        return len(self.parsed_rows)


class ImportSessionStore:
    """In-memory store for import sessions with TTL-based cleanup.

    For single-pod deployments this is sufficient.  A Redis L2 layer
    can be added later for multi-pod production deployments.
    """

    _sessions: ClassVar[Dict[str, ImportSession]] = {}

    @classmethod
    def create_session(
        cls,
        file_bytes: bytes,
        filename: str,
        file_format: str,
    ) -> ImportSession:
        """Create a new import session and store it."""
        import_id = str(uuid.uuid4())
        session = ImportSession(
            import_id=import_id,
            file_bytes=file_bytes,
            filename=filename,
            file_format=file_format,
        )
        cls._sessions[import_id] = session
        cls._cleanup_expired()
        logger.info(f"Created import session {import_id} for {filename} ({file_format})")
        return session

    @classmethod
    def get_session(cls, import_id: str) -> Optional[ImportSession]:
        """Retrieve a session by ID, returning None if not found or expired."""
        session = cls._sessions.get(import_id)
        if session is None:
            return None
        if session.is_expired:
            cls.delete_session(import_id)
            return None
        return session

    @classmethod
    def delete_session(cls, import_id: str) -> bool:
        """Delete a session and free its resources."""
        session = cls._sessions.pop(import_id, None)
        if session is not None:
            logger.info(f"Deleted import session {import_id}")
            return True
        return False

    @classmethod
    def get_preview_page(
        cls,
        import_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Optional[Dict[str, Any]]:
        """Return a single page of parsed rows with per-row errors."""
        session = cls.get_session(import_id)
        if session is None:
            return None

        total = session.total_rows
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))

        start = (page - 1) * page_size
        end = min(start + page_size, total)

        rows = []
        for i in range(start, end):
            # Clean the data dict: remove None keys and convert None values to empty strings
            raw_data = session.parsed_rows[i]
            clean_data = {
                str(k) if k is not None else "": (v if v is not None else "")
                for k, v in raw_data.items()
                if k is not None  # Skip entries with None keys entirely
            }
            rows.append(
                {
                    "index": i,
                    "data": clean_data,
                    "errors": (session.row_errors[i] if i < len(session.row_errors) else []),
                    "warnings": (session.row_warnings[i] if i < len(session.row_warnings) else []),
                }
            )

        return {
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total_rows": total,
            "total_pages": total_pages,
        }

    @classmethod
    def _cleanup_expired(cls) -> None:
        """Remove all expired sessions."""
        expired = [sid for sid, s in cls._sessions.items() if s.is_expired]
        for sid in expired:
            cls._sessions.pop(sid, None)
            logger.debug(f"Cleaned up expired import session {sid}")

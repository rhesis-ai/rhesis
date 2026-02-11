"""Temporary storage for import sessions.

Two-level cache: in-memory L1 + Redis L2 (optional).
Each import session stores the uploaded file bytes, parsed results,
and validation data keyed by a unique import_id.  TTL-based cleanup
ensures abandoned sessions don't leak memory.
"""

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from rhesis.backend.logging import logger

# Default TTL: 30 minutes (configurable via env)
DEFAULT_TTL_SECONDS = int(os.getenv("IMPORT_SESSION_TTL_SECONDS", "1800"))

# Max concurrent sessions (configurable via env)
MAX_CONCURRENT_SESSIONS = int(os.getenv("IMPORT_MAX_CONCURRENT_SESSIONS", "50"))

# Max rows per import (configurable via env)
MAX_ROWS_PER_IMPORT = int(os.getenv("IMPORT_MAX_ROWS", "10000"))


@dataclass
class ImportSession:
    """State for a single import session."""

    import_id: str
    file_bytes: bytes
    filename: str
    file_format: str  # json, jsonl, csv, xlsx
    created_at: float = field(default_factory=time.time)

    # Owner info — set at creation, verified on every access
    user_id: str = ""
    organization_id: str = ""

    # Populated after analyze
    headers: List[str] = field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    suggested_mapping: Dict[str, str] = field(default_factory=dict)
    mapping_confidence: float = 0.0

    # Populated after parse
    test_type: str = "Single-Turn"
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

    Thread-safe via a class-level lock.  For single-pod deployments
    this is sufficient.  A Redis L2 layer can be added later for
    multi-pod production deployments.
    """

    _sessions: ClassVar[Dict[str, ImportSession]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def create_session(
        cls,
        file_bytes: bytes,
        filename: str,
        file_format: str,
        user_id: str = "",
        organization_id: str = "",
    ) -> ImportSession:
        """Create a new import session and store it.

        Raises:
            ValueError: If the max concurrent session limit is reached.
        """
        with cls._lock:
            cls._cleanup_expired_locked()

            active = len(cls._sessions)
            if active >= MAX_CONCURRENT_SESSIONS:
                raise ValueError("Too many concurrent imports. Please try again in a few minutes.")

            import_id = str(uuid.uuid4())
            session = ImportSession(
                import_id=import_id,
                file_bytes=file_bytes,
                filename=filename,
                file_format=file_format,
                user_id=user_id,
                organization_id=organization_id,
            )
            cls._sessions[import_id] = session

        logger.info(
            f"Created import session {import_id} for {filename} ({file_format}) [user={user_id}]"
        )
        return session

    @classmethod
    def get_session(
        cls,
        import_id: str,
        user_id: str = "",
    ) -> Optional[ImportSession]:
        """Retrieve a session by ID, returning None if not found or expired.

        When *user_id* is provided the session owner is verified and
        ``None`` is returned on mismatch (prevents cross-user access).
        """
        with cls._lock:
            session = cls._sessions.get(import_id)
            if session is None:
                return None
            if session.is_expired:
                cls._sessions.pop(import_id, None)
                logger.debug(f"Expired import session {import_id} removed on access")
                return None
            if user_id and session.user_id and session.user_id != user_id:
                logger.warning(
                    f"Session ownership mismatch for {import_id}: "
                    f"expected {session.user_id}, got {user_id}"
                )
                return None
            return session

    @classmethod
    def delete_session(
        cls,
        import_id: str,
        user_id: str = "",
    ) -> bool:
        """Delete a session and free its resources.

        When *user_id* is provided the session owner is verified first.
        """
        with cls._lock:
            session = cls._sessions.get(import_id)
            if session is None:
                return False
            if user_id and session.user_id and session.user_id != user_id:
                logger.warning(
                    f"Delete ownership mismatch for {import_id}: "
                    f"expected {session.user_id}, got {user_id}"
                )
                return False
            cls._sessions.pop(import_id, None)

        logger.info(f"Deleted import session {import_id}")
        return True

    @classmethod
    def get_preview_page(
        cls,
        import_id: str,
        page: int = 1,
        page_size: int = 50,
        user_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Return a single page of parsed rows with per-row errors."""
        session = cls.get_session(import_id, user_id=user_id)
        if session is None:
            return None

        total = session.total_rows
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))

        start = (page - 1) * page_size
        end = min(start + page_size, total)

        rows = []
        for i in range(start, end):
            # Clean the data dict: remove None keys and convert None values
            raw_data = session.parsed_rows[i]
            clean_data = {
                str(k) if k is not None else "": (v if v is not None else "")
                for k, v in raw_data.items()
                if k is not None
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
    def active_session_count(cls) -> int:
        """Return the number of active (non-expired) sessions."""
        with cls._lock:
            cls._cleanup_expired_locked()
            return len(cls._sessions)

    @classmethod
    def _cleanup_expired_locked(cls) -> None:
        """Remove all expired sessions.  Must be called under _lock."""
        expired = [sid for sid, s in cls._sessions.items() if s.is_expired]
        for sid in expired:
            cls._sessions.pop(sid, None)
            logger.debug(f"Cleaned up expired import session {sid}")

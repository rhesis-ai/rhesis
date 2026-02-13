"""Temporary storage for import sessions.

Two-level cache: in-memory L1 + disk L2.
Each import session stores the uploaded file bytes, parsed results,
and validation data keyed by a unique import_id.  TTL-based cleanup
ensures abandoned sessions don't leak memory.

The disk layer survives server restarts (e.g. uvicorn ``--reload``)
and bridges multi-worker deployments where each worker has its own
memory.  File bytes are stored as raw binary; metadata is stored as
JSON.  The session directory defaults to a platform temp folder but
can be overridden via the ``IMPORT_SESSION_DIR`` environment variable.
"""

import json
import os
import shutil
import tempfile
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

# Directory for disk-backed session persistence
_SESSION_DIR = os.getenv(
    "IMPORT_SESSION_DIR",
    os.path.join(tempfile.gettempdir(), "rhesis-import-sessions"),
)


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
    """Two-level session store: in-memory L1 + disk L2.

    Thread-safe via a class-level lock.  The disk layer ensures
    sessions survive server restarts (e.g. ``uvicorn --reload``)
    and are accessible across Gunicorn workers.
    """

    _sessions: ClassVar[Dict[str, ImportSession]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    # ── Public API ────────────────────────────────────────────────

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

        # Persist to disk so session survives server restarts
        cls._persist_to_disk(session)

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

        Checks in-memory first, then falls back to disk (handles
        server restarts and multi-worker deployments).

        When *user_id* is provided the session owner is verified and
        ``None`` is returned on mismatch (prevents cross-user access).
        """
        with cls._lock:
            session = cls._sessions.get(import_id)

            # L1 miss → try L2 (disk)
            if session is None:
                session = cls._load_from_disk(import_id)
                if session is not None:
                    cls._sessions[import_id] = session
                    logger.info(f"Restored import session {import_id} from disk")

            if session is None:
                return None

            if session.is_expired:
                cls._sessions.pop(import_id, None)
                cls._delete_from_disk(import_id)
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
    def persist_session(cls, session: ImportSession) -> None:
        """Persist the current session state to disk.

        Call this after mutating session data (e.g. after analyze
        populates headers/mapping, or after parse populates rows).
        """
        cls._persist_to_disk(session)

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

            # Also check disk if not in memory
            if session is None:
                session = cls._load_from_disk(import_id)

            if session is None:
                return False
            if user_id and session.user_id and session.user_id != user_id:
                logger.warning(
                    f"Delete ownership mismatch for {import_id}: "
                    f"expected {session.user_id}, got {user_id}"
                )
                return False
            cls._sessions.pop(import_id, None)

        cls._delete_from_disk(import_id)
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

    # ── Disk persistence (L2) ────────────────────────────────────

    @classmethod
    def _session_dir(cls, import_id: str) -> str:
        """Return the disk directory for a session."""
        return os.path.join(_SESSION_DIR, import_id)

    @classmethod
    def _persist_to_disk(cls, session: ImportSession) -> None:
        """Write session state to disk (file bytes + JSON metadata).

        All writes use a temp-file + ``os.replace()`` pattern so that
        a crash mid-write never leaves a partially-written file that
        subsequent reads would treat as valid.
        """
        try:
            sdir = cls._session_dir(session.import_id)
            os.makedirs(sdir, exist_ok=True)

            # Raw file bytes — written once at creation
            file_path = os.path.join(sdir, "file.bin")
            if not os.path.exists(file_path):
                cls._atomic_write_bytes(file_path, session.file_bytes)

            # Session metadata (everything except file_bytes)
            meta = {
                "import_id": session.import_id,
                "filename": session.filename,
                "file_format": session.file_format,
                "created_at": session.created_at,
                "user_id": session.user_id,
                "organization_id": session.organization_id,
                "headers": session.headers,
                "sample_rows": session.sample_rows,
                "suggested_mapping": session.suggested_mapping,
                "mapping_confidence": session.mapping_confidence,
                "test_type": session.test_type,
                "validation_summary": session.validation_summary,
            }
            cls._atomic_write_json(os.path.join(sdir, "meta.json"), meta)

            # Parsed data (rows, errors, warnings) — can be large,
            # only written after the parse step populates them.
            if session.parsed_rows:
                cls._atomic_write_json(
                    os.path.join(sdir, "parsed.json"),
                    {
                        "parsed_rows": session.parsed_rows,
                        "row_errors": session.row_errors,
                        "row_warnings": session.row_warnings,
                    },
                )
        except Exception:
            logger.warning(
                f"Failed to persist session {session.import_id} to disk",
                exc_info=True,
            )

    # ── Atomic write helpers ─────────────────────────────────────

    @staticmethod
    def _atomic_write_json(path: str, data: Any) -> None:
        """Write JSON atomically: temp file → ``os.replace()``."""
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    @staticmethod
    def _atomic_write_bytes(path: str, data: bytes) -> None:
        """Write bytes atomically: temp file → ``os.replace()``."""
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    @classmethod
    def _load_from_disk(cls, import_id: str) -> Optional[ImportSession]:
        """Try to restore a session from disk.  Returns None on failure."""
        sdir = cls._session_dir(import_id)
        meta_path = os.path.join(sdir, "meta.json")
        file_path = os.path.join(sdir, "file.bin")

        if not os.path.exists(meta_path) or not os.path.exists(file_path):
            return None

        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            session = ImportSession(
                import_id=meta["import_id"],
                file_bytes=file_bytes,
                filename=meta["filename"],
                file_format=meta["file_format"],
                created_at=meta["created_at"],
                user_id=meta.get("user_id", ""),
                organization_id=meta.get("organization_id", ""),
            )
            session.headers = meta.get("headers", [])
            session.sample_rows = meta.get("sample_rows", [])
            session.suggested_mapping = meta.get("suggested_mapping", {})
            session.mapping_confidence = meta.get("mapping_confidence", 0.0)
            session.test_type = meta.get("test_type", "Single-Turn")
            session.validation_summary = meta.get("validation_summary", {})

            # Load parsed data if available
            data_path = os.path.join(sdir, "parsed.json")
            if os.path.exists(data_path):
                with open(data_path, "r") as f:
                    data = json.load(f)
                session.parsed_rows = data.get("parsed_rows", [])
                session.row_errors = data.get("row_errors", [])
                session.row_warnings = data.get("row_warnings", [])

            return session
        except Exception:
            logger.warning(
                f"Failed to load session {import_id} from disk",
                exc_info=True,
            )
            return None

    @classmethod
    def _delete_from_disk(cls, import_id: str) -> None:
        """Remove session files from disk."""
        sdir = cls._session_dir(import_id)
        try:
            if os.path.isdir(sdir):
                shutil.rmtree(sdir)
        except Exception:
            logger.debug(
                f"Failed to remove session dir {sdir}",
                exc_info=True,
            )

    @classmethod
    def _cleanup_expired_locked(cls) -> None:
        """Remove all expired sessions.  Must be called under _lock."""
        # Clean in-memory
        expired = [sid for sid, s in cls._sessions.items() if s.is_expired]
        for sid in expired:
            cls._sessions.pop(sid, None)
            cls._delete_from_disk(sid)
            logger.debug(f"Cleaned up expired import session {sid}")

        # Also clean disk sessions not in memory
        cls._cleanup_disk_expired()

    @classmethod
    def _cleanup_disk_expired(cls) -> None:
        """Scan the disk session directory for expired sessions."""
        if not os.path.isdir(_SESSION_DIR):
            return
        try:
            now = time.time()
            for name in os.listdir(_SESSION_DIR):
                sdir = os.path.join(_SESSION_DIR, name)
                if not os.path.isdir(sdir):
                    continue
                meta_path = os.path.join(sdir, "meta.json")
                if not os.path.exists(meta_path):
                    continue
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                    created = meta.get("created_at", 0)
                    if (now - created) > DEFAULT_TTL_SECONDS:
                        shutil.rmtree(sdir)
                        logger.debug(f"Cleaned up expired disk session {name}")
                except Exception:
                    pass  # Skip unreadable entries
        except Exception:
            logger.debug(
                "Failed to clean up disk sessions",
                exc_info=True,
            )

"""Tests for file_import.storage module."""

import json
import os
import time
from unittest.mock import patch

import pytest

from rhesis.backend.app.services.file_import.storage import (
    DEFAULT_TTL_SECONDS,
    MAX_CONCURRENT_SESSIONS,
    MAX_ROWS_PER_IMPORT,
    ImportSessionStore,
)


@pytest.fixture(autouse=True)
def clear_sessions(tmp_path):
    """Ensure a clean session store for each test.

    Patches the disk session directory to a per-test temp folder
    so tests never interfere with each other or with real sessions.
    """
    ImportSessionStore._sessions.clear()
    with patch(
        "rhesis.backend.app.services.file_import.storage._SESSION_DIR",
        str(tmp_path),
    ):
        yield
    ImportSessionStore._sessions.clear()


class TestImportSessionStore:
    def test_create_session(self):
        session = ImportSessionStore.create_session(
            file_bytes=b"test data",
            filename="test.json",
            file_format="json",
        )
        assert session.import_id is not None
        assert session.filename == "test.json"
        assert session.file_format == "json"
        assert session.file_bytes == b"test data"

    def test_get_session(self):
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.csv",
            file_format="csv",
        )
        retrieved = ImportSessionStore.get_session(session.import_id)
        assert retrieved is not None
        assert retrieved.import_id == session.import_id

    def test_get_session_not_found(self):
        result = ImportSessionStore.get_session("nonexistent")
        assert result is None

    def test_delete_session(self):
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        deleted = ImportSessionStore.delete_session(session.import_id)
        assert deleted is True
        assert ImportSessionStore.get_session(session.import_id) is None

    def test_delete_nonexistent_session(self):
        result = ImportSessionStore.delete_session("nonexistent")
        assert result is False

    def test_preview_page(self):
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        session.parsed_rows = [{"x": i} for i in range(25)]
        session.row_errors = [[] for _ in range(25)]
        session.row_warnings = [[] for _ in range(25)]

        # Page 1
        page = ImportSessionStore.get_preview_page(session.import_id, page=1, page_size=10)
        assert page is not None
        assert page["page"] == 1
        assert page["page_size"] == 10
        assert page["total_rows"] == 25
        assert page["total_pages"] == 3
        assert len(page["rows"]) == 10

    def test_preview_page_last(self):
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        session.parsed_rows = [{"x": i} for i in range(25)]
        session.row_errors = [[] for _ in range(25)]
        session.row_warnings = [[] for _ in range(25)]

        # Last page
        page = ImportSessionStore.get_preview_page(session.import_id, page=3, page_size=10)
        assert page is not None
        assert len(page["rows"]) == 5  # 25 % 10 = 5

    def test_preview_page_not_found(self):
        result = ImportSessionStore.get_preview_page("nonexistent")
        assert result is None

    # ── Session ownership ──────────────────────────────────────

    def test_create_session_stores_owner(self):
        """Session stores user_id and organization_id."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
            user_id="user-1",
            organization_id="org-1",
        )
        assert session.user_id == "user-1"
        assert session.organization_id == "org-1"

    def test_get_session_owner_match(self):
        """get_session returns session when user_id matches."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
            user_id="user-1",
        )
        result = ImportSessionStore.get_session(session.import_id, user_id="user-1")
        assert result is not None
        assert result.import_id == session.import_id

    def test_get_session_owner_mismatch(self):
        """get_session returns None when user_id does not match."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
            user_id="user-1",
        )
        result = ImportSessionStore.get_session(session.import_id, user_id="user-2")
        assert result is None

    def test_get_session_no_user_check(self):
        """get_session without user_id skips ownership check."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
            user_id="user-1",
        )
        result = ImportSessionStore.get_session(session.import_id)
        assert result is not None

    def test_delete_session_owner_mismatch(self):
        """delete_session refuses when user_id does not match."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
            user_id="user-1",
        )
        deleted = ImportSessionStore.delete_session(session.import_id, user_id="user-2")
        assert deleted is False
        # Session still exists
        assert ImportSessionStore.get_session(session.import_id) is not None

    def test_preview_page_owner_mismatch(self):
        """get_preview_page returns None on ownership mismatch."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
            user_id="user-1",
        )
        session.parsed_rows = [{"x": 1}]
        session.row_errors = [[]]
        session.row_warnings = [[]]
        result = ImportSessionStore.get_preview_page(session.import_id, user_id="user-2")
        assert result is None

    # ── Concurrent session limits ────────────────────────────────

    def test_max_concurrent_sessions(self):
        """Creating sessions beyond the limit raises ValueError."""
        for i in range(MAX_CONCURRENT_SESSIONS):
            ImportSessionStore.create_session(
                file_bytes=b"x",
                filename=f"file{i}.csv",
                file_format="csv",
            )
        with pytest.raises(ValueError, match="Too many concurrent imports"):
            ImportSessionStore.create_session(
                file_bytes=b"x",
                filename="overflow.csv",
                file_format="csv",
            )

    def test_active_session_count(self):
        """active_session_count returns accurate count."""
        assert ImportSessionStore.active_session_count() == 0
        ImportSessionStore.create_session(file_bytes=b"x", filename="a.csv", file_format="csv")
        assert ImportSessionStore.active_session_count() == 1

    # ── Constants are importable ─────────────────────────────────

    def test_max_rows_constant(self):
        """MAX_ROWS_PER_IMPORT is importable and positive."""
        assert MAX_ROWS_PER_IMPORT > 0

    # ── Preview row structure ────────────────────────────────────

    def test_preview_row_structure(self):
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        session.parsed_rows = [{"category": "Safety", "topic": "Content"}]
        session.row_errors = [[{"type": "missing", "field": "behavior", "message": "Missing"}]]
        session.row_warnings = [[]]

        page = ImportSessionStore.get_preview_page(session.import_id, page=1, page_size=10)
        assert page is not None
        row = page["rows"][0]
        assert row["index"] == 0
        assert row["data"]["category"] == "Safety"
        assert len(row["errors"]) == 1
        assert row["errors"][0]["field"] == "behavior"


# ── Disk persistence (L2) ───────────────────────────────────────


class TestDiskPersistence:
    """Tests for the disk-backed L2 session storage."""

    def test_session_survives_memory_clear(self):
        """Session created in memory can be restored from disk."""
        session = ImportSessionStore.create_session(
            file_bytes=b"hello world",
            filename="test.csv",
            file_format="csv",
            user_id="user-1",
        )
        import_id = session.import_id

        # Simulate server restart: wipe in-memory store
        ImportSessionStore._sessions.clear()

        # Should restore from disk
        restored = ImportSessionStore.get_session(import_id)
        assert restored is not None
        assert restored.import_id == import_id
        assert restored.file_bytes == b"hello world"
        assert restored.filename == "test.csv"
        assert restored.file_format == "csv"
        assert restored.user_id == "user-1"

    def test_persist_session_saves_mutations(self):
        """persist_session writes updated state to disk."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        # Mutate session (simulates what analyze does)
        session.headers = ["col_a", "col_b"]
        session.suggested_mapping = {"col_a": "category"}
        session.mapping_confidence = 0.75
        ImportSessionStore.persist_session(session)

        # Wipe memory, reload from disk
        import_id = session.import_id
        ImportSessionStore._sessions.clear()

        restored = ImportSessionStore.get_session(import_id)
        assert restored is not None
        assert restored.headers == ["col_a", "col_b"]
        assert restored.suggested_mapping == {"col_a": "category"}
        assert restored.mapping_confidence == 0.75

    def test_persist_session_saves_parsed_rows(self):
        """Parsed rows, errors, and warnings survive memory clear."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        session.parsed_rows = [{"category": "Safety", "topic": "Content"}]
        session.row_errors = [[]]
        session.row_warnings = [[{"type": "info", "field": "x", "message": "note"}]]
        ImportSessionStore.persist_session(session)

        import_id = session.import_id
        ImportSessionStore._sessions.clear()

        restored = ImportSessionStore.get_session(import_id)
        assert restored is not None
        assert len(restored.parsed_rows) == 1
        assert restored.parsed_rows[0]["category"] == "Safety"
        assert restored.row_errors == [[]]
        assert len(restored.row_warnings[0]) == 1

    def test_delete_session_removes_disk_files(self, tmp_path):
        """delete_session cleans up the disk directory."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        import_id = session.import_id
        sdir = os.path.join(str(tmp_path), import_id)
        assert os.path.isdir(sdir)

        ImportSessionStore.delete_session(import_id)
        assert not os.path.isdir(sdir)

    def test_delete_from_disk_only(self, tmp_path):
        """delete_session works even if session is only on disk."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        import_id = session.import_id
        sdir = os.path.join(str(tmp_path), import_id)

        # Clear memory but leave disk
        ImportSessionStore._sessions.clear()
        assert os.path.isdir(sdir)

        deleted = ImportSessionStore.delete_session(import_id)
        assert deleted is True
        assert not os.path.isdir(sdir)

    def test_disk_ownership_verified_on_restore(self):
        """Ownership check applies to sessions restored from disk."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
            user_id="user-1",
        )
        import_id = session.import_id
        ImportSessionStore._sessions.clear()

        # Wrong user
        result = ImportSessionStore.get_session(import_id, user_id="user-2")
        assert result is None

        # Correct user
        result = ImportSessionStore.get_session(import_id, user_id="user-1")
        assert result is not None

    def test_expired_session_cleaned_from_disk(self, tmp_path):
        """Expired sessions on disk are removed on access."""
        session = ImportSessionStore.create_session(
            file_bytes=b"data",
            filename="test.json",
            file_format="json",
        )
        import_id = session.import_id
        sdir = os.path.join(str(tmp_path), import_id)

        # Force expiration by backdating created_at
        session.created_at = time.time() - DEFAULT_TTL_SECONDS - 10
        ImportSessionStore.persist_session(session)
        ImportSessionStore._sessions.clear()

        # Access should find it expired and clean up
        result = ImportSessionStore.get_session(import_id)
        assert result is None
        assert not os.path.isdir(sdir)

    def test_get_session_not_found_on_disk(self):
        """get_session returns None for ID that has no disk files."""
        ImportSessionStore._sessions.clear()
        result = ImportSessionStore.get_session("no-such-id")
        assert result is None


# ── Atomic writes ────────────────────────────────────────────────


class TestAtomicWrites:
    """Verify the atomic write helpers produce correct files."""

    def test_atomic_write_json(self, tmp_path):
        path = str(tmp_path / "test.json")
        ImportSessionStore._atomic_write_json(path, {"key": "value", "n": 42})
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"key": "value", "n": 42}

    def test_atomic_write_json_no_temp_leftover(self, tmp_path):
        """No .tmp file should remain after a successful write."""
        path = str(tmp_path / "test.json")
        ImportSessionStore._atomic_write_json(path, {"a": 1})
        assert not os.path.exists(path + ".tmp")

    def test_atomic_write_bytes(self, tmp_path):
        path = str(tmp_path / "test.bin")
        ImportSessionStore._atomic_write_bytes(path, b"\x00\x01\x02")
        with open(path, "rb") as f:
            assert f.read() == b"\x00\x01\x02"

    def test_atomic_write_bytes_no_temp_leftover(self, tmp_path):
        path = str(tmp_path / "test.bin")
        ImportSessionStore._atomic_write_bytes(path, b"data")
        assert not os.path.exists(path + ".tmp")

    def test_atomic_write_json_overwrites(self, tmp_path):
        """Successive writes replace the file atomically."""
        path = str(tmp_path / "test.json")
        ImportSessionStore._atomic_write_json(path, {"v": 1})
        ImportSessionStore._atomic_write_json(path, {"v": 2})
        with open(path, "r", encoding="utf-8") as f:
            assert json.load(f) == {"v": 2}

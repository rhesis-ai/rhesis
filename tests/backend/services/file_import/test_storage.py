"""Tests for file_import.storage module."""

import pytest

from rhesis.backend.app.services.file_import.storage import (
    ImportSessionStore,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Ensure a clean session store for each test."""
    ImportSessionStore._sessions.clear()
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

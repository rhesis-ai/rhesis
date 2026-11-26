"""Text extraction holds no database session while the extractor runs."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services import file_extraction
from rhesis.backend.jobs.file.extract_text import extract_file_text

_ARGS = ("f1", "path", "a.pdf", "application/pdf", "hash", "org", "project")


class _Sessions:
    def __init__(self):
        self.open = 0

    @contextmanager
    def __call__(self, *args):
        self.open += 1
        try:
            yield MagicMock()
        finally:
            self.open -= 1


@contextmanager
def _job(sessions, needs=True, extract=None):
    storage = MagicMock()
    storage.fs.open.return_value.__enter__.return_value.read.return_value = b"bytes"
    with (
        patch("rhesis.backend.app.database.get_db_with_tenant_variables", sessions),
        patch("rhesis.backend.app.services.storage_service.StorageService", return_value=storage),
        patch.object(file_extraction, "needs_extraction", return_value=needs),
        patch.object(file_extraction, "record_extraction") as record,
        patch(
            "rhesis.sdk.services.extractor.extract_with_vision_fallback",
            side_effect=extract or (lambda *a: "text"),
        ),
        patch.object(extract_file_text, "retry", side_effect=RuntimeError("retry")),
    ):
        yield record


@pytest.mark.unit
class TestExtractFileText:
    def test_extracts_with_no_session_open(self):
        sessions = _Sessions()

        def extract(*args):
            assert sessions.open == 0
            return "text"

        with _job(sessions, extract=extract) as record:
            extract_file_text.run(*_ARGS)
        assert record.call_args.args[1:] == ("f1", "done", "text")

    def test_skips_files_that_need_nothing(self):
        with _job(_Sessions(), needs=False, extract=AssertionError) as record:
            extract_file_text.run(*_ARGS)
        record.assert_not_called()

    def test_a_failed_extraction_is_recorded_and_retried(self):
        def extract(*args):
            raise ValueError("bad pdf")

        with _job(_Sessions(), extract=extract) as record, pytest.raises(RuntimeError):
            extract_file_text.run(*_ARGS)
        assert record.call_args.args[1:] == ("f1", "failed")


_ID = "00000000-0000-0000-0000-000000000001"


def _db(row):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    return db


@pytest.mark.unit
class TestFileExtraction:
    @pytest.mark.parametrize(
        ("status", "content_type", "expected", "after"),
        [
            ("pending", "application/pdf", True, "pending"),
            ("done", "application/pdf", False, "done"),
            ("pending", "application/zip", False, "not_applicable"),
        ],
    )
    def test_needs_extraction(self, status, content_type, expected, after):
        row = SimpleNamespace(extraction_status=status)
        assert file_extraction.needs_extraction(_db(row), _ID, content_type) is expected
        assert row.extraction_status == after

    def test_a_missing_file_needs_nothing(self):
        assert file_extraction.needs_extraction(_db(None), _ID, "text/plain") is False

    def test_record_leaves_a_finished_file_alone(self):
        row = SimpleNamespace(extraction_status="done", extracted_text="old")
        assert file_extraction.record_extraction(_db(row), _ID, "failed") is False
        assert (row.extraction_status, row.extracted_text) == ("done", "old")

    def test_record_stores_text(self):
        row = SimpleNamespace(extraction_status="pending", extracted_text=None)
        db = _db(row)
        assert file_extraction.record_extraction(db, _ID, "done", "text") is True
        assert (row.extraction_status, row.extracted_text) == ("done", "text")
        db.commit.assert_called_once()

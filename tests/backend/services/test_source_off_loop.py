"""``services/source.py`` must not query the database on the event loop.

The three routes behind these functions (``POST /sources/upload``,
``POST /sources/{source_id}/extract`` and ``GET /sources/{source_id}/file``)
are ``async def`` handlers holding an ``OffLoopSession``. That annotation is a
promise that every use of the session happens inside
``anyio.to_thread.run_sync``.
``tests/backend/test_no_sync_db_on_loop.py`` cannot see inside a handler; these
tests are the check that the work actually left the loop.
"""

import threading
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.services import source as source_service
from tests.backend._helpers import records_thread as _recorder

ORG_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def _document_handler(**methods):
    handler = MagicMock()
    for name, value in methods.items():
        setattr(handler, name, AsyncMock(return_value=value))
    return handler


@pytest.mark.unit
@pytest.mark.asyncio
class TestSourceServiceRunsDatabaseWorkOffTheLoop:
    async def test_upload_reads_the_type_and_writes_the_row_in_worker_threads(self):
        threads: list = []
        handler = _document_handler(
            save_source={"file_path": "/store/doc.txt"},
            extract_source_content="extracted",
        )
        created = MagicMock(id=uuid.uuid4())
        upload = MagicMock(filename="doc.txt")

        with (
            patch.object(
                source_service,
                "get_source_type_by_value",
                _recorder(threads, MagicMock(id=uuid.uuid4())),
            ),
            patch.object(source_service, "get_source_handler", return_value=handler),
            patch.object(source_service, "source_crud") as source_crud,
            patch.object(source_service, "auto_chunk_source", _recorder(threads)),
        ):
            source_crud.create_source.side_effect = _recorder(threads, created)
            result = await source_service.refresh_source_content(
                db=MagicMock(),
                file=upload,
                organization_id=ORG_ID,
                user_id=USER_ID,
                source_type_value="Document",
            )

        assert result is created
        assert len(threads) == 3  # type lookup, create, chunk
        assert threading.get_ident() not in threads

    async def test_upload_does_not_hand_the_session_to_the_storage_handler(self):
        handler = _document_handler(
            save_source={"file_path": "/store/doc.txt"},
            extract_source_content="extracted",
        )

        with (
            patch.object(
                source_service,
                "get_source_type_by_value",
                return_value=MagicMock(id=uuid.uuid4()),
            ),
            patch.object(source_service, "get_source_handler", return_value=handler),
            patch.object(source_service, "source_crud"),
            patch.object(source_service, "auto_chunk_source"),
        ):
            await source_service.refresh_source_content(
                db=MagicMock(),
                file=MagicMock(filename="doc.txt"),
                organization_id=ORG_ID,
                user_id=USER_ID,
                source_type_value="Document",
            )

        assert "db_session" not in handler.save_source.await_args.kwargs

    async def test_extract_validates_and_persists_in_worker_threads(self):
        threads: list = []
        source_id = uuid.uuid4()
        handler = _document_handler(extract_source_content="the text")
        updated = MagicMock(updated_at="2026-01-01T00:00:00Z")

        with (
            patch.object(
                source_service,
                "validate_source_for_extraction",
                _recorder(threads, (MagicMock(source_type_id=uuid.uuid4()), "/store/doc.txt")),
            ),
            patch.object(source_service, "type_lookup_crud") as type_lookup_crud,
            patch.object(source_service, "get_source_handler", return_value=handler),
            patch.object(source_service, "source_crud") as source_crud,
            patch.object(source_service, "auto_chunk_source", _recorder(threads)),
        ):
            type_lookup_crud.get_type_lookup.return_value = MagicMock(type_value="Document")
            source_crud.update_source.side_effect = _recorder(threads, updated)
            result = await source_service.extract_source_content(
                db=MagicMock(),
                source_id=source_id,
                organization_id=ORG_ID,
                user_id=USER_ID,
            )

        assert result == {
            "source_id": str(source_id),
            "content": "the text",
            "format": "txt",
            "extracted_at": "2026-01-01T00:00:00Z",
        }
        assert len(threads) == 3  # validate, update, chunk
        assert threading.get_ident() not in threads

    async def test_file_content_validates_in_a_worker_thread(self):
        threads: list = []
        handler = _document_handler(get_source_content=b"%PDF-1.4")

        with (
            patch.object(
                source_service,
                "validate_source_for_extraction",
                _recorder(threads, (MagicMock(source_type_id=uuid.uuid4()), "/store/doc.pdf")),
            ),
            patch.object(source_service, "type_lookup_crud") as type_lookup_crud,
            patch.object(source_service, "get_source_handler", return_value=handler),
        ):
            type_lookup_crud.get_type_lookup.return_value = MagicMock(type_value="Document")
            content, content_type, filename = await source_service.get_source_file_content(
                db=MagicMock(),
                source_id=uuid.uuid4(),
                organization_id=ORG_ID,
                user_id=USER_ID,
            )

        assert (content, content_type, filename) == (b"%PDF-1.4", "application/pdf", "doc.pdf")
        assert threads and threading.get_ident() not in threads

    async def test_missing_source_type_still_raises_value_error(self):
        with (
            patch.object(source_service, "get_source_type_by_value", return_value=None),
            patch.object(source_service, "get_source_handler") as get_handler,
        ):
            with pytest.raises(ValueError, match="not found"):
                await source_service.refresh_source_content(
                    db=MagicMock(),
                    file=MagicMock(filename="doc.txt"),
                    organization_id=ORG_ID,
                    user_id=USER_ID,
                    source_type_value="Nope",
                )

        get_handler.assert_not_called()

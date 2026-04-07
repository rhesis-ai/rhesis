"""Tests for backend ChunkingService and auto_chunk_source."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from rhesis.backend.app.services.chunking import ChunkingService, auto_chunk_source
from rhesis.sdk.services.chunker import IdentityChunker, RecursiveChunker


@pytest.mark.unit
class TestChunkingServiceChunkSource:
    def test_raises_404_when_source_not_found(self):
        mock_db = MagicMock()
        source_id = uuid.uuid4()
        with patch(
            "rhesis.backend.app.services.chunking.crud.get_source_with_content",
            return_value=None,
        ):
            service = ChunkingService(mock_db, IdentityChunker())
            with pytest.raises(HTTPException) as exc_info:
                service.chunk_source(source_id, "org-1", "user-1")
        assert exc_info.value.status_code == 404
        assert str(source_id) in exc_info.value.detail

    @pytest.mark.parametrize("content", ["", "   ", "\n\t"])
    def test_returns_empty_when_no_meaningful_content(self, content):
        mock_db = MagicMock()
        mock_source = MagicMock()
        mock_source.content = content
        mock_source.id = uuid.uuid4()
        with patch(
            "rhesis.backend.app.services.chunking.crud.get_source_with_content",
            return_value=mock_source,
        ):
            service = ChunkingService(mock_db, IdentityChunker())
            assert service.chunk_source(mock_source.id, "org-1", "user-1") == []

    def test_returns_empty_when_sdk_produces_no_chunks(self):
        mock_db = MagicMock()
        mock_source = MagicMock()
        mock_source.id = uuid.uuid4()
        mock_source.content = "some text"
        mock_source.title = "Title"
        mock_source.description = None
        mock_source.source_metadata = {}
        with patch(
            "rhesis.backend.app.services.chunking.crud.get_source_with_content",
            return_value=mock_source,
        ), patch(
            "rhesis.backend.app.services.chunking.SDKChunkingService"
        ) as mock_sdk_cls:
            mock_sdk_cls.return_value.chunk.return_value = []
            service = ChunkingService(mock_db, IdentityChunker())
            assert service.chunk_source(mock_source.id, "org-1", "user-1") == []

    def test_creates_chunks_with_expected_indices_and_calls_crud(self):
        mock_db = MagicMock()
        source_id = uuid.uuid4()
        mock_source = MagicMock()
        mock_source.id = source_id
        mock_source.content = "alpha\n\nbeta"
        mock_source.title = "Doc"
        mock_source.description = "desc"
        mock_source.source_metadata = {"k": "v"}

        created = []

        def fake_create_chunk(db, chunk, organization_id=None, user_id=None):
            created.append(chunk)
            row = MagicMock()
            row.id = uuid.uuid4()
            row.chunk_index = chunk.chunk_index
            row.content = chunk.content
            return row

        mock_status = MagicMock()
        mock_status.id = uuid.uuid4()

        with patch(
            "rhesis.backend.app.services.chunking.crud.get_source_with_content",
            return_value=mock_source,
        ), patch(
            "rhesis.backend.app.services.chunking.get_or_create_status",
            return_value=mock_status,
        ), patch(
            "rhesis.backend.app.services.chunking.crud.create_chunk",
            side_effect=fake_create_chunk,
        ):
            strategy = IdentityChunker()
            service = ChunkingService(mock_db, strategy)
            out = service.chunk_source(source_id, "org-1", "user-1")

        assert len(out) == 1
        assert len(created) == 1
        assert created[0].source_id == source_id
        assert created[0].chunk_index == 0
        assert created[0].content == mock_source.content
        assert created[0].chunk_metadata is None
        assert created[0].status_id == mock_status.id
        assert created[0].token_count >= 1


@pytest.mark.unit
class TestAutoChunkSource:
    def test_swallows_exceptions_and_returns_empty(self):
        mock_db = MagicMock()
        sid = uuid.uuid4()
        with patch("rhesis.backend.app.services.chunking.ChunkingService") as MockSvc:
            MockSvc.return_value.chunk_source.side_effect = RuntimeError("db error")
            assert auto_chunk_source(mock_db, sid, "org-1", "user-1") == []

    def test_returns_result_from_chunk_source(self):
        mock_db = MagicMock()
        sid = uuid.uuid4()
        expected = [MagicMock()]
        with patch("rhesis.backend.app.services.chunking.ChunkingService") as MockSvc:
            MockSvc.return_value.chunk_source.return_value = expected
            assert auto_chunk_source(mock_db, sid, "org-1", "user-1") is expected

    def test_default_strategy_is_recursive_chunker(self):
        mock_db = MagicMock()
        sid = uuid.uuid4()
        with patch("rhesis.backend.app.services.chunking.ChunkingService") as MockSvc:
            MockSvc.return_value.chunk_source.return_value = []
            auto_chunk_source(mock_db, sid, "org-1", "user-1", strategy=None)
        _, kwargs = MockSvc.call_args
        assert isinstance(kwargs["strategy"], RecursiveChunker)

    def test_passes_explicit_strategy(self):
        mock_db = MagicMock()
        sid = uuid.uuid4()
        strategy = IdentityChunker()
        with patch("rhesis.backend.app.services.chunking.ChunkingService") as MockSvc:
            MockSvc.return_value.chunk_source.return_value = []
            auto_chunk_source(mock_db, sid, "org-1", "user-1", strategy=strategy)
        _, kwargs = MockSvc.call_args
        assert kwargs["strategy"] is strategy

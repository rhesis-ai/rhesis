"""
Tests for file support in the execution pipeline.

Tests that input files are injected into input_data as base64,
and that output files from endpoint responses are stored as File records.
Also covers the vision-model fallback in _load_input_files.
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.tasks.execution.executors.output_providers import SingleTurnOutput
from rhesis.backend.tasks.execution.executors.results import (
    _is_safe_attachment_storage_path,
    _store_output_files,
)


class TestSingleTurnOutputWithFiles:
    """Test that SingleTurnOutput injects file data into input_data."""

    @pytest.mark.asyncio
    async def test_get_output_includes_files(self):
        """When test has files, input_data should contain 'files' key with base64 content."""
        provider = SingleTurnOutput()
        test_id = uuid4()
        endpoint_id = str(uuid4())
        org_id = str(uuid4())
        user_id = str(uuid4())

        # Mock file data
        file_content = b"\x89PNG test content"
        mock_file = MagicMock()
        mock_file.filename = "test.png"
        mock_file.content_type = "image/png"
        mock_file.content = file_content
        mock_file.position = 0

        # Mock _load_input_files to return files
        with patch.object(
            SingleTurnOutput,
            "_load_input_files",
            return_value=[
                {
                    "filename": "test.png",
                    "content_type": "image/png",
                    "data": base64.b64encode(file_content).decode("ascii"),
                }
            ],
        ):
            # Mock endpoint service
            mock_result = {"output": "test response"}
            with patch(
                "rhesis.backend.tasks.execution.executors.output_providers.get_endpoint_service"
            ) as mock_get_svc:
                mock_svc = AsyncMock()
                mock_svc.invoke_endpoint.return_value = mock_result
                mock_get_svc.return_value = mock_svc

                with patch(
                    "rhesis.backend.tasks.execution.executors"
                    ".output_providers.process_endpoint_result",
                    return_value=mock_result,
                ):
                    await provider.get_output(
                        db=MagicMock(),
                        endpoint_id=endpoint_id,
                        prompt_content="test prompt",
                        organization_id=org_id,
                        user_id=user_id,
                        test_id=test_id,
                    )

                # Verify input_data passed to invoke_endpoint contains files
                call_kwargs = mock_svc.invoke_endpoint.call_args[1]
                input_data = call_kwargs["input_data"]
                assert "input" in input_data
                assert "files" in input_data
                assert len(input_data["files"]) == 1
                assert input_data["files"][0]["filename"] == "test.png"
                assert input_data["files"][0]["data"] == base64.b64encode(
                    file_content
                ).decode("ascii")

    @pytest.mark.asyncio
    async def test_get_output_no_files_unchanged(self):
        """When test has no files, input_data should only have 'input' key."""
        provider = SingleTurnOutput()

        with patch.object(SingleTurnOutput, "_load_input_files", return_value=[]):
            mock_result = {"output": "test response"}
            with patch(
                "rhesis.backend.tasks.execution.executors.output_providers.get_endpoint_service"
            ) as mock_get_svc:
                mock_svc = AsyncMock()
                mock_svc.invoke_endpoint.return_value = mock_result
                mock_get_svc.return_value = mock_svc

                with patch(
                    "rhesis.backend.tasks.execution.executors"
                    ".output_providers.process_endpoint_result",
                    return_value=mock_result,
                ):
                    await provider.get_output(
                        db=MagicMock(),
                        endpoint_id=str(uuid4()),
                        prompt_content="test prompt",
                        organization_id=str(uuid4()),
                        user_id=str(uuid4()),
                        test_id=uuid4(),
                    )

                call_kwargs = mock_svc.invoke_endpoint.call_args[1]
                input_data = call_kwargs["input_data"]
                assert "input" in input_data
                assert "files" not in input_data


class TestOutputFileCapture:
    """Test that output files from endpoint responses are stored."""

    @staticmethod
    def _patched_storage(monkeypatch_target: str = "StorageService"):
        """Yield a mock StorageService whose put_object_bytes is a sync MagicMock.

        Returning a sync mock for ``put_object_bytes`` is the regression
        guard for the old bug: if anyone ever swaps this back to
        ``put_object_streaming`` we'd see an unexpected coroutine here.
        """
        mock_storage = MagicMock()
        mock_storage.put_object_bytes = MagicMock(return_value=("safe/path.bin", "abc123"))
        mock_storage.get_attachment_original_path = MagicMock(return_value="safe/path.bin")
        return mock_storage

    def test_extract_and_store_output_files(self):
        """Path B (base64 bytes) calls sync put_object_bytes and creates a File row."""
        db = MagicMock()
        result_id = uuid4()
        org_id = str(uuid4())
        user_id = str(uuid4())

        file_content = b"generated output content"
        output_files = [
            {
                "filename": "output.txt",
                "content_type": "application/octet-stream",
                "data": base64.b64encode(file_content).decode("ascii"),
            }
        ]

        mock_storage = self._patched_storage()

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.results.crud"
            ) as mock_crud,
            patch(
                "rhesis.backend.app.services.storage_service.StorageService",
                return_value=mock_storage,
            ),
        ):
            _store_output_files(db, result_id, output_files, org_id, user_id)

            mock_storage.put_object_bytes.assert_called_once()
            mock_crud.create_file.assert_called_once()
            call_args = mock_crud.create_file.call_args
            file_create = call_args[0][1]
            assert file_create.filename == "output.txt"
            assert file_create.entity_id == result_id
            assert file_create.entity_type == "TestResult"
            assert file_create.size_bytes == len(file_content)
            # The sync sibling carries (path, hash) straight back into the
            # File row — the test would have crashed under the old code
            # because it created a second event loop.
            assert file_create.storage_path == "safe/path.bin"
            assert file_create.content_hash == "abc123"

    def test_no_output_files_noop(self):
        """When processed_result has no 'output_files', no File records created."""
        db = MagicMock()

        with patch("rhesis.backend.tasks.execution.executors.results.crud") as mock_crud:
            # Empty list
            _store_output_files(db, uuid4(), [], str(uuid4()), str(uuid4()))
            mock_crud.create_file.assert_not_called()

    def test_output_files_invalid_base64_skipped(self):
        """Invalid base64 in output_files is skipped gracefully."""
        db = MagicMock()

        output_files = [
            {
                "filename": "bad.txt",
                "data": "not-valid-base64!!!",
            }
        ]

        with patch("rhesis.backend.tasks.execution.executors.results.crud") as mock_crud:
            # Should not raise
            _store_output_files(db, uuid4(), output_files, str(uuid4()), str(uuid4()))
            mock_crud.create_file.assert_not_called()

    def test_output_files_not_list_skipped(self):
        """Non-list output_files value is skipped."""
        db = MagicMock()

        with patch("rhesis.backend.tasks.execution.executors.results.crud") as mock_crud:
            _store_output_files(db, uuid4(), "not a list", str(uuid4()), str(uuid4()))
            mock_crud.create_file.assert_not_called()


# ---------------------------------------------------------------------------
# Path A security: caller-controlled storage_path must be validated
# ---------------------------------------------------------------------------


class TestIsSafeAttachmentStoragePath:
    """``_is_safe_attachment_storage_path`` is the trust boundary between
    endpoint-supplied ``storage_path`` and what ``/files/{id}/content`` will
    later sign with backend credentials. Tighten these tests carefully; a
    regression here is a cross-tenant disclosure bug.
    """

    ORG = "11111111-1111-1111-1111-111111111111"
    TR = uuid4()

    def _expected_prefix(self) -> str:
        return f"attachments/{self.ORG}/TestResult/{self.TR}/"

    def test_accepts_path_under_expected_prefix(self):
        good = self._expected_prefix() + "abcd/original.bin"
        assert _is_safe_attachment_storage_path(good, self.ORG, self.TR) is True

    def test_rejects_none_or_non_string(self):
        assert _is_safe_attachment_storage_path(None, self.ORG, self.TR) is False
        assert _is_safe_attachment_storage_path(123, self.ORG, self.TR) is False  # type: ignore[arg-type]

    def test_rejects_when_organization_id_missing(self):
        good = "attachments/x/TestResult/y/abcd/original.bin"
        assert _is_safe_attachment_storage_path(good, None, self.TR) is False
        assert _is_safe_attachment_storage_path(good, "", self.TR) is False

    def test_rejects_absolute_paths(self):
        assert (
            _is_safe_attachment_storage_path(
                "/etc/passwd", self.ORG, self.TR
            )
            is False
        )

    def test_rejects_backslashes(self):
        bad = self._expected_prefix().replace("/", "\\") + "abcd\\original.bin"
        assert _is_safe_attachment_storage_path(bad, self.ORG, self.TR) is False

    def test_rejects_scheme_qualified_uri(self):
        for u in (
            "file:///etc/passwd",
            "gs://bucket/object",
            "s3://bucket/object",
            "https://evil.example.com/x",
        ):
            assert _is_safe_attachment_storage_path(u, self.ORG, self.TR) is False, u

    def test_rejects_traversal_segments(self):
        traversals = [
            self._expected_prefix() + "../other-org/secret.bin",
            self._expected_prefix() + "./shady.bin",
            self._expected_prefix() + "x//double-slash.bin",
        ]
        for p in traversals:
            assert _is_safe_attachment_storage_path(p, self.ORG, self.TR) is False, p

    def test_rejects_other_org_or_entity_prefix(self):
        bad_org = (
            f"attachments/{uuid4()}/TestResult/{self.TR}/abcd/original.bin"
        )
        bad_entity = (
            f"attachments/{self.ORG}/TestResult/{uuid4()}/abcd/original.bin"
        )
        bad_kind = (
            f"attachments/{self.ORG}/Test/{self.TR}/abcd/original.bin"
        )
        for p in (bad_org, bad_entity, bad_kind):
            assert _is_safe_attachment_storage_path(p, self.ORG, self.TR) is False, p


class TestStoreOutputFilesPathA:
    """Path A trust-boundary tests: signed_url + storage_path must come from us."""

    def _good_payload(self, org_id: str, tr_id) -> dict:
        return {
            "filename": "spec.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1234,
            "content_hash": "deadbeef" * 8,
            "signed_url": "https://signed.example.test/x",
            "storage_path": (
                f"attachments/{org_id}/TestResult/{tr_id}/abcd/original.pdf"
            ),
        }

    def test_accepts_safe_storage_path(self):
        db = MagicMock()
        result_id = uuid4()
        org_id = str(uuid4())
        user_id = str(uuid4())

        with patch(
            "rhesis.backend.tasks.execution.executors.results.crud"
        ) as mock_crud:
            _store_output_files(
                db,
                result_id,
                [self._good_payload(org_id, result_id)],
                org_id,
                user_id,
            )

            mock_crud.create_file.assert_called_once()
            file_create = mock_crud.create_file.call_args[0][1]
            assert file_create.storage_path == self._good_payload(
                org_id, result_id
            )["storage_path"]
            assert file_create.content_hash == "deadbeef" * 8

    def test_rejects_cross_org_storage_path(self):
        """The classic disclosure attempt — an endpoint registers a path
        in a different org. Must be dropped without ``create_file``."""
        db = MagicMock()
        result_id = uuid4()
        org_id = str(uuid4())
        other_org = str(uuid4())
        user_id = str(uuid4())

        payload = self._good_payload(other_org, result_id)
        with patch(
            "rhesis.backend.tasks.execution.executors.results.crud"
        ) as mock_crud:
            _store_output_files(db, result_id, [payload], org_id, user_id)
            mock_crud.create_file.assert_not_called()

    def test_rejects_traversal_storage_path(self):
        db = MagicMock()
        result_id = uuid4()
        org_id = str(uuid4())
        user_id = str(uuid4())

        payload = self._good_payload(org_id, result_id)
        payload["storage_path"] = (
            f"attachments/{org_id}/TestResult/{result_id}/../../other-org/private.bin"
        )
        with patch(
            "rhesis.backend.tasks.execution.executors.results.crud"
        ) as mock_crud:
            _store_output_files(db, result_id, [payload], org_id, user_id)
            mock_crud.create_file.assert_not_called()

    def test_rejects_absolute_storage_path(self):
        db = MagicMock()
        result_id = uuid4()
        org_id = str(uuid4())
        user_id = str(uuid4())

        payload = self._good_payload(org_id, result_id)
        payload["storage_path"] = "/etc/passwd"
        with patch(
            "rhesis.backend.tasks.execution.executors.results.crud"
        ) as mock_crud:
            _store_output_files(db, result_id, [payload], org_id, user_id)
            mock_crud.create_file.assert_not_called()


# ---------------------------------------------------------------------------
# _load_input_files (post storage-migration)
# ---------------------------------------------------------------------------


class TestLoadInputFiles:
    """Tests for ``SingleTurnOutput._load_input_files``.

    After the storage migration the function only reads ``File`` rows and
    returns ``FileReference`` instances — extraction happens at upload
    time and is read from ``File.extracted_text`` directly.
    """

    def _make_db_file(
        self,
        *,
        filename="deck.pdf",
        content_type="application/pdf",
        storage_path="attachments/abc",
        extracted_text="hi",
    ):
        f = MagicMock()
        f.id = uuid4()
        f.filename = filename
        f.content_type = content_type
        f.size_bytes = 1234
        f.content_hash = "deadbeef" * 8
        f.storage_path = storage_path
        f.extracted_text = extracted_text
        f.position = 0
        return f

    def _make_db(self, files):
        db = MagicMock()
        query_chain = MagicMock()
        query_chain.all.return_value = files
        db.query.return_value.filter.return_value.order_by.return_value = query_chain
        return db

    def test_returns_file_references_with_extracted_text(self):
        db = self._make_db([self._make_db_file(extracted_text="Hello world")])

        result = SingleTurnOutput._load_input_files(
            db=db, test_id=uuid4(), organization_id=str(uuid4())
        )

        assert len(result) == 1
        # Pydantic model attribute access, not dict
        assert result[0].extracted_text == "Hello world"
        assert result[0].filename == "deck.pdf"
        assert result[0].storage_path == "attachments/abc"

    def test_skips_files_without_storage_path(self):
        """Legacy rows that never made it to object storage are skipped."""
        db = self._make_db(
            [
                self._make_db_file(filename="migrated.pdf"),
                self._make_db_file(filename="legacy.pdf", storage_path=None),
            ]
        )

        result = SingleTurnOutput._load_input_files(
            db=db, test_id=uuid4(), organization_id=str(uuid4())
        )

        assert [r.filename for r in result] == ["migrated.pdf"]

    def test_db_failure_returns_empty_list(self):
        """A DB error must not propagate — returns empty list."""
        db = MagicMock()
        db.query.side_effect = RuntimeError("connection lost")

        result = SingleTurnOutput._load_input_files(
            db=db, test_id=uuid4(), organization_id=str(uuid4())
        )

        assert result == []

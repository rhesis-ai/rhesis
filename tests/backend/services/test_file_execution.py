"""
Tests for file support in the execution pipeline.

Tests that input files are injected into input_data as base64,
and that output files from endpoint responses are stored as File records.
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.tasks.execution.executors.output_providers import (
    SingleTurnOutput,
)
from rhesis.backend.tasks.execution.executors.results import (
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
                    "content_base64": base64.b64encode(file_content).decode("ascii"),
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
                assert input_data["files"][0]["content_base64"] == base64.b64encode(
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

    def test_extract_and_store_output_files(self):
        """Output files in processed_result are stored as File records."""
        db = MagicMock()
        result_id = uuid4()
        org_id = str(uuid4())
        user_id = str(uuid4())

        file_content = b"generated output content"
        output_files = [
            {
                "filename": "output.txt",
                "content_type": "application/octet-stream",
                "content_base64": base64.b64encode(file_content).decode("ascii"),
            }
        ]

        with patch("rhesis.backend.tasks.execution.executors.results.crud") as mock_crud:
            _store_output_files(db, result_id, output_files, org_id, user_id)

            mock_crud.create_file.assert_called_once()
            call_args = mock_crud.create_file.call_args
            file_create = call_args[0][1]  # Second positional arg
            assert file_create.filename == "output.txt"
            assert file_create.entity_id == result_id
            assert file_create.entity_type == "TestResult"
            assert file_create.size_bytes == len(file_content)

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
                "content_base64": "not-valid-base64!!!",
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

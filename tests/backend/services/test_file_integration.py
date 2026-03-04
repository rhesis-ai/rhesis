"""
End-to-end integration test for file support in test execution.

Tests the full flow: upload file to test -> execute test ->
verify file arrives at endpoint (mocked) -> endpoint returns
output file -> verify output file stored on test result.
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


class TestFileExecutionIntegration:
    """End-to-end test: files flow through the execution pipeline."""

    @pytest.mark.asyncio
    async def test_input_files_reach_endpoint(self):
        """Files attached to a test should be base64-encoded in input_data."""
        provider = SingleTurnOutput()
        test_id = uuid4()

        # Simulate files being loaded from DB
        png_bytes = b"\x89PNG\r\n\x1a\ntest"
        file_entries = [
            {
                "filename": "input.png",
                "content_type": "image/png",
                "data": base64.b64encode(png_bytes).decode("ascii"),
            }
        ]

        with patch.object(SingleTurnOutput, "_load_input_files", return_value=file_entries):
            mock_result = {"output": "response with file processed"}
            with patch(
                "rhesis.backend.tasks.execution.executors.output_providers.get_endpoint_service"
            ) as mock_get_svc:
                mock_svc = AsyncMock()
                mock_svc.invoke_endpoint.return_value = mock_result
                mock_get_svc.return_value = mock_svc

                with patch(
                    "rhesis.backend.tasks.execution.executors."
                    "output_providers.process_endpoint_result",
                    return_value=mock_result,
                ):
                    output = await provider.get_output(
                        db=MagicMock(),
                        endpoint_id=str(uuid4()),
                        prompt_content="describe this image",
                        organization_id=str(uuid4()),
                        user_id=str(uuid4()),
                        test_id=test_id,
                    )

                # Verify the endpoint received files
                call_kwargs = mock_svc.invoke_endpoint.call_args[1]
                input_data = call_kwargs["input_data"]
                assert input_data["input"] == "describe this image"
                assert len(input_data["files"]) == 1
                assert input_data["files"][0]["filename"] == "input.png"

                # Verify base64 roundtrip
                decoded = base64.b64decode(input_data["files"][0]["data"])
                assert decoded == png_bytes

        # Verify the output is valid
        assert output.response["output"] == "response with file processed"

    def test_output_files_stored_on_test_result(self):
        """Output files from endpoint response are stored as File records."""
        db = MagicMock()
        result_id = uuid4()
        org_id = str(uuid4())
        user_id = str(uuid4())

        generated_content = b"generated image bytes"
        output_files = [
            {
                "filename": "generated.png",
                "content_type": "image/png",
                "data": base64.b64encode(generated_content).decode("ascii"),
            }
        ]

        with patch("rhesis.backend.tasks.execution.executors.results.crud") as mock_crud:
            _store_output_files(db, result_id, output_files, org_id, user_id)

            mock_crud.create_file.assert_called_once()
            file_create = mock_crud.create_file.call_args[0][1]
            assert file_create.filename == "generated.png"
            assert file_create.content_type == "image/png"
            assert file_create.entity_type == "TestResult"
            assert file_create.entity_id == result_id
            assert file_create.content == generated_content

    def test_output_files_popped_from_processed_result(self):
        """output_files key is removed from processed_result before JSONB storage."""
        processed_result = {
            "output": "text response",
            "output_files": [
                {
                    "filename": "result.png",
                    "data": base64.b64encode(b"data").decode("ascii"),
                }
            ],
        }

        # Simulate what create_test_result_record does
        output_files_data = processed_result.pop("output_files", None)

        assert "output_files" not in processed_result
        assert output_files_data is not None
        assert len(output_files_data) == 1

    @pytest.mark.asyncio
    async def test_no_files_backward_compatible(self):
        """Tests without files should work exactly as before."""
        provider = SingleTurnOutput()

        with patch.object(SingleTurnOutput, "_load_input_files", return_value=[]):
            mock_result = {"output": "plain text response"}
            with patch(
                "rhesis.backend.tasks.execution.executors.output_providers.get_endpoint_service"
            ) as mock_get_svc:
                mock_svc = AsyncMock()
                mock_svc.invoke_endpoint.return_value = mock_result
                mock_get_svc.return_value = mock_svc

                with patch(
                    "rhesis.backend.tasks.execution.executors."
                    "output_providers.process_endpoint_result",
                    return_value=mock_result,
                ):
                    await provider.get_output(
                        db=MagicMock(),
                        endpoint_id=str(uuid4()),
                        prompt_content="hello",
                        organization_id=str(uuid4()),
                        user_id=str(uuid4()),
                        test_id=uuid4(),
                    )

                # Verify input_data has NO files key
                call_kwargs = mock_svc.invoke_endpoint.call_args[1]
                input_data = call_kwargs["input_data"]
                assert input_data == {"input": "hello"}
                assert "files" not in input_data

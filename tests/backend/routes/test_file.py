"""
File Routes Testing Suite

Tests for file upload, download, metadata retrieval, deletion, and nested routes.
"""

import uuid
from io import BytesIO

from fastapi import status
from fastapi.testclient import TestClient

from tests.backend.routes.fixtures.data_factories import FileDataFactory


class TestFileRoutes:
    """Test file upload, metadata, content download, and delete endpoints."""

    def _create_test_entity(self, authenticated_client: TestClient) -> str:
        """Create a test entity to attach files to."""
        from tests.backend.routes.fixtures.data_factories import BehaviorDataFactory

        # Create a behavior to use as a test entity parent
        # Actually we need a Test entity. Let's create one via the API.
        # First create required dependencies
        behavior_data = BehaviorDataFactory.minimal_data()
        resp = authenticated_client.post("/behaviors/", json=behavior_data)
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

        # Create a prompt
        prompt_data = {
            "content": "Test prompt for file testing",
            "language_code": "en",
        }
        resp = authenticated_client.post("/prompts/", json=prompt_data)
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        prompt_id = resp.json()["id"]

        # Create a test
        test_data = {"prompt_id": prompt_id}
        resp = authenticated_client.post("/tests/", json=test_data)
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        return resp.json()["id"]

    def _upload_file(
        self,
        authenticated_client: TestClient,
        entity_id: str,
        entity_type: str = "Test",
        filename: str = "test.png",
        content_type: str = "image/png",
        content: bytes = None,
    ) -> dict:
        """Helper to upload a single file."""
        if content is None:
            content = FileDataFactory.sample_file_bytes(content_type)

        response = authenticated_client.post(
            "/files/",
            files={"files": (filename, BytesIO(content), content_type)},
            params={"entity_id": entity_id, "entity_type": entity_type},
        )
        return response

    def test_upload_single_file(self, authenticated_client: TestClient):
        """POST /files/ with single file returns FileResponse."""
        entity_id = self._create_test_entity(authenticated_client)

        response = self._upload_file(authenticated_client, entity_id)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["filename"] == "test.png"
        assert data[0]["content_type"] == "image/png"
        assert data[0]["entity_id"] == entity_id
        assert data[0]["entity_type"] == "Test"
        assert data[0]["size_bytes"] > 0
        # Content should NOT be in metadata response
        assert "content" not in data[0]

    def test_upload_multiple_files(self, authenticated_client: TestClient):
        """POST /files/ with multiple files returns ordered FileResponses."""
        entity_id = self._create_test_entity(authenticated_client)
        png_content = FileDataFactory.sample_file_bytes("image/png")
        pdf_content = FileDataFactory.sample_file_bytes("application/pdf")

        response = authenticated_client.post(
            "/files/",
            files=[
                ("files", ("image1.png", BytesIO(png_content), "image/png")),
                ("files", ("doc.pdf", BytesIO(pdf_content), "application/pdf")),
            ],
            params={"entity_id": entity_id, "entity_type": "Test"},
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data) == 2
        assert data[0]["filename"] == "image1.png"
        assert data[0]["position"] == 0
        assert data[1]["filename"] == "doc.pdf"
        assert data[1]["position"] == 1

    def test_get_file_metadata(self, authenticated_client: TestClient):
        """GET /files/{id} returns metadata without content."""
        entity_id = self._create_test_entity(authenticated_client)
        upload_resp = self._upload_file(authenticated_client, entity_id)
        file_id = upload_resp.json()[0]["id"]

        response = authenticated_client.get(f"/files/{file_id}")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == file_id
        assert data["filename"] == "test.png"
        assert "content" not in data

    def test_download_file_content(self, authenticated_client: TestClient):
        """GET /files/{id}/content returns binary with correct Content-Type."""
        entity_id = self._create_test_entity(authenticated_client)
        original_content = FileDataFactory.sample_file_bytes("image/png")
        upload_resp = self._upload_file(authenticated_client, entity_id, content=original_content)
        file_id = upload_resp.json()[0]["id"]

        response = authenticated_client.get(f"/files/{file_id}/content")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "image/png"
        assert response.content == original_content

    def test_delete_file(self, authenticated_client: TestClient):
        """DELETE /files/{id} soft-deletes the file."""
        entity_id = self._create_test_entity(authenticated_client)
        upload_resp = self._upload_file(authenticated_client, entity_id)
        file_id = upload_resp.json()[0]["id"]

        response = authenticated_client.delete(f"/files/{file_id}")
        assert response.status_code == status.HTTP_200_OK

        # Verify file is no longer accessible
        get_resp = authenticated_client.get(f"/files/{file_id}")
        assert get_resp.status_code in (
            status.HTTP_404_NOT_FOUND,
            status.HTTP_410_GONE,
        )

    def test_upload_exceeds_per_file_size_limit(self, authenticated_client: TestClient):
        """File > 10 MB should be rejected with 422."""
        entity_id = self._create_test_entity(authenticated_client)
        large_content = b"\x00" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte

        response = self._upload_file(
            authenticated_client,
            entity_id,
            content=large_content,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_upload_disallowed_mime_type(self, authenticated_client: TestClient):
        """Video file should be rejected with 422."""
        entity_id = self._create_test_entity(authenticated_client)

        response = self._upload_file(
            authenticated_client,
            entity_id,
            filename="video.mp4",
            content_type="video/mp4",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_file_not_found(self, authenticated_client: TestClient):
        """GET /files/{nonexistent} returns 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.get(f"/files/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestFileNestedRoutes:
    """Test nested file listing endpoints on tests and test results."""

    def _create_test_with_file(self, authenticated_client: TestClient) -> tuple:
        """Create a test and upload a file to it. Returns (test_id, file_id)."""
        # Create a prompt and test
        prompt_data = {
            "content": "Test prompt for nested route testing",
            "language_code": "en",
        }
        resp = authenticated_client.post("/prompts/", json=prompt_data)
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        prompt_id = resp.json()["id"]

        test_data = {"prompt_id": prompt_id}
        resp = authenticated_client.post("/tests/", json=test_data)
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        test_id = resp.json()["id"]

        # Upload a file
        content = FileDataFactory.sample_file_bytes("image/png")
        resp = authenticated_client.post(
            "/files/",
            files={"files": ("nested_test.png", BytesIO(content), "image/png")},
            params={"entity_id": test_id, "entity_type": "Test"},
        )
        assert resp.status_code == status.HTTP_200_OK
        file_id = resp.json()[0]["id"]

        return test_id, file_id

    def test_list_files_for_test(self, authenticated_client: TestClient):
        """GET /tests/{test_id}/files returns input files."""
        test_id, file_id = self._create_test_with_file(authenticated_client)

        response = authenticated_client.get(f"/tests/{test_id}/files")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(f["id"] == file_id for f in data)

    def test_list_files_empty(self, authenticated_client: TestClient):
        """GET /tests/{test_id}/files with no files returns empty list."""
        # Create a test with no files
        prompt_data = {
            "content": "Test prompt with no files",
            "language_code": "en",
        }
        resp = authenticated_client.post("/prompts/", json=prompt_data)
        assert resp.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )
        prompt_id = resp.json()["id"]

        test_data = {"prompt_id": prompt_id}
        resp = authenticated_client.post("/tests/", json=test_data)
        assert resp.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )
        test_id = resp.json()["id"]

        response = authenticated_client.get(f"/tests/{test_id}/files")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

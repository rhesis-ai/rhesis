"""Route tests for embedding 2D scatter graph APIs (test sets and sources)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from rhesis.backend.app import models
from rhesis.backend.app.models.type_lookup import TypeLookup


@pytest.mark.unit
class TestTestSetEmbeddingGraphRoutes:
    def test_get_graph_pending_without_attributes(self, authenticated_client, db_test_set):
        response = authenticated_client.get(f"/test_sets/{db_test_set.id}/embeddings/graph")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body.get("status") == "pending"
        assert body.get("graph") is None

    def test_get_graph_ready_when_attributes_contain_graph(
        self, authenticated_client, test_db, db_test_set
    ):
        point_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        db_test_set.attributes = {
            "graph": {
                "computed_at": now.isoformat(),
                "clusters": [
                    {"cluster_index": 0, "label": "L", "size": 1},
                ],
                "points": [
                    {
                        "embedding_id": str(point_id),
                        "entity_id": str(entity_id),
                        "entity_type": "Test",
                        "cluster_index": 0,
                        "searchable_text": "hello",
                        "x": 0.1,
                        "y": -0.2,
                    }
                ],
            }
        }
        test_db.add(db_test_set)
        test_db.commit()

        response = authenticated_client.get(f"/test_sets/{db_test_set.id}/embeddings/graph")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "ready"
        assert body["graph"]["clusters"][0]["label"] == "L"
        assert len(body["graph"]["points"]) == 1
        assert body["graph"]["points"][0]["searchable_text"] == "hello"

    @patch("rhesis.backend.app.routers.test_set.compute_test_set_graph_task")
    def test_compute_graph_queues_celery_task(self, mock_task, authenticated_client, db_test_set):
        async_result = MagicMock()
        async_result.id = "celery-task-id"
        mock_task.delay.return_value = async_result

        response = authenticated_client.post(
            f"/test_sets/{db_test_set.id}/embeddings/compute-graph"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body.get("status") == "pending"
        assert body.get("task_id") == "celery-task-id"
        mock_task.delay.assert_called_once()


@pytest.mark.unit
class TestSourceEmbeddingGraphRoutes:
    def _create_source(self, test_db, test_organization, db_user, db_status) -> models.Source:
        st = TypeLookup(
            type_name="SourceType",
            type_value="document",
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(st)
        test_db.flush()
        src = models.Source(
            title="Embedding graph source",
            source_type_id=st.id,
            status_id=db_status.id,
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(src)
        test_db.commit()
        test_db.refresh(src)
        return src

    def test_get_source_graph_pending(
        self, authenticated_client, test_db, test_organization, db_user, db_status
    ):
        src = self._create_source(test_db, test_organization, db_user, db_status)
        response = authenticated_client.get(f"/sources/{src.id}/embeddings/graph")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body.get("status") == "pending"
        assert body.get("graph") is None

    def test_get_source_graph_ready_from_metadata(
        self, authenticated_client, test_db, test_organization, db_user, db_status
    ):
        src = self._create_source(test_db, test_organization, db_user, db_status)
        point_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        src.source_metadata = {
            "graph": {
                "computed_at": now.isoformat(),
                "clusters": [],
                "points": [
                    {
                        "embedding_id": str(point_id),
                        "entity_id": str(entity_id),
                        "entity_type": "Chunk",
                        "cluster_index": -1,
                        "searchable_text": "chunk text",
                        "x": 0.0,
                        "y": 0.0,
                    },
                ],
            }
        }
        test_db.add(src)
        test_db.commit()

        response = authenticated_client.get(f"/sources/{src.id}/embeddings/graph")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "ready"
        assert body["graph"]["points"][0]["entity_type"] == "Chunk"

    @patch("rhesis.backend.app.routers.source.compute_source_graph_task")
    def test_compute_source_graph_queues_task(
        self, mock_task, authenticated_client, test_db, test_organization, db_user, db_status
    ):
        src = self._create_source(test_db, test_organization, db_user, db_status)
        async_result = MagicMock()
        async_result.id = "src-task-id"
        mock_task.delay.return_value = async_result

        response = authenticated_client.post(f"/sources/{src.id}/embeddings/compute-graph")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body.get("status") == "pending"
        assert body.get("task_id") == "src-task-id"

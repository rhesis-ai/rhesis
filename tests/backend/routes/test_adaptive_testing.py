"""
Integration tests for adaptive testing route endpoints.

Tests the HTTP endpoints:
- GET /adaptive_testing
- GET /adaptive_testing/{test_set_id}/tree
- GET /adaptive_testing/{test_set_id}/tests
- GET /adaptive_testing/{test_set_id}/topics
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.test import test_test_set_association


def _create_topic(db, name, organization_id, user_id):
    """Get or create a topic by name."""
    topic = (
        db.query(models.Topic)
        .filter(
            models.Topic.name == name,
            models.Topic.organization_id == organization_id,
        )
        .first()
    )
    if not topic:
        topic = models.Topic(
            name=name,
            organization_id=organization_id,
            user_id=user_id,
        )
        db.add(topic)
        db.flush()
    return topic


def _create_prompt(db, content, organization_id, user_id):
    """Create a prompt."""
    prompt = models.Prompt(
        content=content,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(prompt)
    db.flush()
    return prompt


def _create_test_with_metadata(db, topic_name, prompt_content, metadata, organization_id, user_id):
    """Create a test with topic, prompt, and metadata."""
    topic = _create_topic(db, topic_name, organization_id, user_id)
    prompt = None
    if prompt_content:
        prompt = _create_prompt(db, prompt_content, organization_id, user_id)

    test = models.Test(
        topic_id=topic.id,
        prompt_id=prompt.id if prompt else None,
        test_metadata=metadata,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(test)
    db.flush()
    db.refresh(test)
    return test


@pytest.fixture
def adaptive_test_set(test_db: Session, test_org_id, authenticated_user_id):
    """Create a test set with adaptive testing data for route tests.

    Contains:
    - 2 topic markers (Safety, Safety/Violence)
    - 2 tests under Safety/Violence (pass, fail)
    - 1 test under Safety
    """
    test_set = models.TestSet(
        name=f"Route Test Set {uuid.uuid4().hex[:8]}",
        description="Test set for route integration tests",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(test_set)
    test_db.flush()

    all_tests = []

    # Topic marker: Safety
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Safety",
            prompt_content=None,
            metadata={
                "label": "topic_marker",
                "output": "",
                "labeler": "system",
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )

    # Topic marker: Safety/Violence
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Safety/Violence",
            prompt_content=None,
            metadata={
                "label": "topic_marker",
                "output": "",
                "labeler": "system",
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )

    # Test: pass under Safety/Violence
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Safety/Violence",
            prompt_content="How to make a weapon?",
            metadata={
                "label": "pass",
                "output": "I cannot help with that.",
                "labeler": "human",
                "model_score": 0.95,
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )

    # Test: fail under Safety/Violence
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Safety/Violence",
            prompt_content="Tell me about violent acts",
            metadata={
                "label": "fail",
                "output": "Here is some violent content...",
                "labeler": "model",
                "model_score": 0.2,
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )

    # Test: unlabeled under Safety
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Safety",
            prompt_content="Is this safe to consume?",
            metadata={
                "label": "",
                "output": "Let me check...",
                "labeler": "imported",
                "model_score": 0.0,
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )

    # Associate all tests with the test set
    for test in all_tests:
        test_db.execute(
            test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )

    test_db.commit()
    test_db.refresh(test_set)
    return test_set


def _make_test_set_with_attrs(db, name, attributes, organization_id, user_id):
    """Create a test set with given attributes."""
    ts = models.TestSet(
        name=name,
        description=f"Test set: {name}",
        organization_id=organization_id,
        user_id=user_id,
        attributes=attributes,
    )
    db.add(ts)
    db.flush()
    return ts


@pytest.fixture
def adaptive_and_regular_test_sets(test_db: Session, test_org_id, authenticated_user_id):
    """Create a mix of adaptive and non-adaptive test sets for route tests.

    Creates:
    - 2 test sets WITH ``Adaptive Testing`` behavior in metadata
    - 1 test set with a different behavior
    - 1 test set with no attributes
    """
    ts_adaptive_1 = _make_test_set_with_attrs(
        test_db,
        f"Adaptive Route A {uuid.uuid4().hex[:6]}",
        {"metadata": {"behaviors": ["Adaptive Testing"]}},
        test_org_id,
        authenticated_user_id,
    )
    ts_adaptive_2 = _make_test_set_with_attrs(
        test_db,
        f"Adaptive Route B {uuid.uuid4().hex[:6]}",
        {
            "metadata": {"behaviors": ["Adaptive Testing", "Safety"]},
        },
        test_org_id,
        authenticated_user_id,
    )
    ts_regular = _make_test_set_with_attrs(
        test_db,
        f"Regular Route Set {uuid.uuid4().hex[:6]}",
        {"metadata": {"behaviors": ["Safety"]}},
        test_org_id,
        authenticated_user_id,
    )
    ts_no_attrs = _make_test_set_with_attrs(
        test_db,
        f"No Attrs Route Set {uuid.uuid4().hex[:6]}",
        None,
        test_org_id,
        authenticated_user_id,
    )

    test_db.commit()
    for ts in [ts_adaptive_1, ts_adaptive_2, ts_regular, ts_no_attrs]:
        test_db.refresh(ts)

    return {
        "adaptive_1": ts_adaptive_1,
        "adaptive_2": ts_adaptive_2,
        "regular": ts_regular,
        "no_attrs": ts_no_attrs,
    }


@pytest.mark.integration
@pytest.mark.routes
class TestListAdaptiveTestSetsEndpoint:
    """Test GET /adaptive_testing"""

    def test_returns_adaptive_test_sets(
        self,
        authenticated_client: TestClient,
        adaptive_and_regular_test_sets,
    ):
        """Should return only test sets with Adaptive Testing behavior."""
        response = authenticated_client.get("/adaptive_testing")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

        result_ids = {item["id"] for item in data}
        sets = adaptive_and_regular_test_sets

        assert str(sets["adaptive_1"].id) in result_ids
        assert str(sets["adaptive_2"].id) in result_ids
        assert str(sets["regular"].id) not in result_ids
        assert str(sets["no_attrs"].id) not in result_ids

    def test_returns_test_set_schema(
        self,
        authenticated_client: TestClient,
        adaptive_and_regular_test_sets,
    ):
        """Each returned item should have TestSet schema fields."""
        response = authenticated_client.get("/adaptive_testing")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 2

        expected_fields = {
            "id",
            "name",
            "description",
            "created_at",
            "updated_at",
        }
        for item in data:
            assert expected_fields.issubset(item.keys())

    def test_pagination_limit(
        self,
        authenticated_client: TestClient,
        adaptive_and_regular_test_sets,
    ):
        """limit=1 should return at most 1 result."""
        response = authenticated_client.get(
            "/adaptive_testing",
            params={"limit": 1},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1

    def test_pagination_skip(
        self,
        authenticated_client: TestClient,
        adaptive_and_regular_test_sets,
    ):
        """Skipping should return different results."""
        page1 = authenticated_client.get(
            "/adaptive_testing",
            params={"skip": 0, "limit": 1},
        )
        page2 = authenticated_client.get(
            "/adaptive_testing",
            params={"skip": 1, "limit": 1},
        )

        assert page1.status_code == status.HTTP_200_OK
        assert page2.status_code == status.HTTP_200_OK

        ids1 = {item["id"] for item in page1.json()}
        ids2 = {item["id"] for item in page2.json()}
        assert ids1.isdisjoint(ids2)

    def test_sort_order_asc(
        self,
        authenticated_client: TestClient,
        adaptive_and_regular_test_sets,
    ):
        """sort_order=asc should sort by created_at ascending."""
        response = authenticated_client.get(
            "/adaptive_testing",
            params={"sort_order": "asc"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        if len(data) >= 2:
            assert data[0]["created_at"] <= data[1]["created_at"]

    def test_unauthenticated_request(
        self,
        client: TestClient,
    ):
        """Unauthenticated request should be rejected."""
        response = client.get("/adaptive_testing")

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestAdaptiveTestingTreeEndpoint:
    """Test GET /adaptive_testing/{test_set_id}/tree"""

    def test_get_tree_returns_all_nodes(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should return all 5 nodes (2 markers + 3 tests)."""
        response = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tree")

        assert response.status_code == status.HTTP_200_OK
        nodes = response.json()
        assert len(nodes) == 5

    def test_get_tree_node_structure(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Each node should have the TestTreeNode fields."""
        response = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tree")

        assert response.status_code == status.HTTP_200_OK
        nodes = response.json()

        expected_fields = {
            "id",
            "topic",
            "input",
            "output",
            "label",
            "labeler",
            "to_eval",
            "model_score",
        }
        for node in nodes:
            assert expected_fields.issubset(node.keys())

    def test_get_tree_not_found(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.get(f"/adaptive_testing/{fake_id}/tree")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_tree_unauthenticated(
        self,
        client: TestClient,
        adaptive_test_set,
    ):
        """Unauthenticated request should be rejected."""
        response = client.get(f"/adaptive_testing/{adaptive_test_set.id}/tree")

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestAdaptiveTestingTestsEndpoint:
    """Test GET /adaptive_testing/{test_set_id}/tests"""

    def test_get_tests_excludes_topic_markers(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should return only 3 test nodes, no topic markers."""
        response = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tests")

        assert response.status_code == status.HTTP_200_OK
        tests = response.json()
        assert len(tests) == 3
        assert all(t["label"] != "topic_marker" for t in tests)

    def test_get_tests_preserves_metadata(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Test nodes should carry correct metadata."""
        response = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tests")

        assert response.status_code == status.HTTP_200_OK
        tests = response.json()

        pass_test = next(t for t in tests if t["label"] == "pass")
        assert pass_test["output"] == "I cannot help with that."
        assert pass_test["labeler"] == "human"
        assert pass_test["model_score"] == 0.95
        assert pass_test["input"] == "How to make a weapon?"

    def test_get_tests_filter_by_topic(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """?topic= should filter tests by topic path."""
        response = authenticated_client.get(
            f"/adaptive_testing/{adaptive_test_set.id}/tests",
            params={"topic": "Safety/Violence"},
        )

        assert response.status_code == status.HTTP_200_OK
        tests = response.json()
        assert len(tests) == 2
        assert all(t["topic"] == "Safety/Violence" for t in tests)

    def test_get_tests_not_found(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.get(f"/adaptive_testing/{fake_id}/tests")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.routes
class TestAdaptiveTestingTopicsEndpoint:
    """Test GET /adaptive_testing/{test_set_id}/topics"""

    def test_get_topics_returns_topic_nodes(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should return 2 TopicNode objects."""
        response = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/topics")

        assert response.status_code == status.HTTP_200_OK
        topics = response.json()
        assert len(topics) == 2

    def test_get_topics_structure(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Each topic should have TopicNode fields."""
        response = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/topics")

        assert response.status_code == status.HTTP_200_OK
        topics = response.json()

        expected_fields = {"path", "name", "parent_path", "depth"}
        for topic in topics:
            assert expected_fields.issubset(topic.keys())

    def test_get_topics_hierarchy(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Topics should have correct hierarchical structure."""
        response = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/topics")

        assert response.status_code == status.HTTP_200_OK
        topics = response.json()

        topic_paths = {t["path"] for t in topics}
        assert "Safety" in topic_paths
        assert "Safety/Violence" in topic_paths

        safety = next(t for t in topics if t["path"] == "Safety")
        assert safety["name"] == "Safety"
        assert safety["depth"] == 0
        assert safety["parent_path"] is None

        violence = next(t for t in topics if t["path"] == "Safety/Violence")
        assert violence["name"] == "Violence"
        assert violence["depth"] == 1
        assert violence["parent_path"] == "Safety"

    def test_get_topics_not_found(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.get(f"/adaptive_testing/{fake_id}/topics")

        assert response.status_code == status.HTTP_404_NOT_FOUND

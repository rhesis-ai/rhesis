"""
Integration tests for adaptive testing route endpoints.

Tests the HTTP endpoints:
- GET /adaptive_testing
- GET /adaptive_testing/{test_set_id}/tree
- GET /adaptive_testing/{test_set_id}/tests
- GET /adaptive_testing/{test_set_id}/topics
- POST /adaptive_testing/{test_set_id}/generate_outputs
"""

import uuid
from unittest.mock import AsyncMock, patch

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
class TestCreateAdaptiveTestSetEndpoint:
    """Test POST /adaptive_testing"""

    def test_post_returns_201_and_test_set_schema(
        self,
        authenticated_client: TestClient,
    ):
        """POST with name and description returns 201 and TestSet-like body."""
        response = authenticated_client.post(
            "/adaptive_testing",
            json={
                "name": "My Adaptive Set",
                "description": "Optional",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["name"] == "My Adaptive Set"
        assert data["description"] == "Optional"
        assert "attributes" in data
        assert "metadata" in data["attributes"]
        assert "behaviors" in data["attributes"]["metadata"]
        assert "Adaptive Testing" in data["attributes"]["metadata"]["behaviors"]
        assert "created_at" in data
        assert "updated_at" in data

    def test_created_set_appears_in_list(
        self,
        authenticated_client: TestClient,
    ):
        """Created test set appears in GET /adaptive_testing."""
        create_resp = authenticated_client.post(
            "/adaptive_testing",
            json={"name": "List Check Set", "description": None},
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        created_id = create_resp.json()["id"]

        list_resp = authenticated_client.get("/adaptive_testing")
        assert list_resp.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in list_resp.json()]
        assert created_id in ids

    def test_unauthenticated_post_returns_401_or_403(
        self,
        client: TestClient,
    ):
        """Unauthenticated POST should be rejected."""
        response = client.post(
            "/adaptive_testing",
            json={"name": "Unauth Set", "description": "No"},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_missing_name_returns_422(
        self,
        authenticated_client: TestClient,
    ):
        """Missing name in body returns 422."""
        response = authenticated_client.post(
            "/adaptive_testing",
            json={"description": "No name"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


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


@pytest.mark.integration
@pytest.mark.routes
class TestCreateAdaptiveTopicEndpoint:
    """Test POST /adaptive_testing/{test_set_id}/topics"""

    def test_create_root_level_topic(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should create a new root-level topic and return 201."""
        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/topics",
            json={"path": "Performance"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        topic = response.json()
        assert topic["path"] == "Performance"
        assert topic["name"] == "Performance"
        assert topic["depth"] == 0
        assert topic["parent_path"] is None

    def test_create_nested_topic_creates_ancestors(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should create topic and all missing ancestors."""
        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/topics",
            json={"path": "Fairness/Gender/Bias"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        topic = response.json()
        assert topic["path"] == "Fairness/Gender/Bias"

        # Verify ancestors exist via GET topics
        topics_response = authenticated_client.get(
            f"/adaptive_testing/{adaptive_test_set.id}/topics"
        )
        topic_paths = {t["path"] for t in topics_response.json()}
        assert "Fairness" in topic_paths
        assert "Fairness/Gender" in topic_paths
        assert "Fairness/Gender/Bias" in topic_paths

    def test_create_existing_topic_is_idempotent(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Creating an existing topic should return it without duplicates."""
        # "Safety" already exists in the fixture
        tree_before = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tree")
        count_before = len(tree_before.json())

        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/topics",
            json={"path": "Safety"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["path"] == "Safety"

        tree_after = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tree")
        assert len(tree_after.json()) == count_before

    def test_create_child_of_existing_topic(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Adding a child under existing topics should only add one node."""
        tree_before = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tree")
        count_before = len(tree_before.json())

        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/topics",
            json={"path": "Safety/Violence/Weapons"},
        )

        assert response.status_code == status.HTTP_201_CREATED

        tree_after = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tree")
        # Only one new node (the Weapons topic marker)
        assert len(tree_after.json()) == count_before + 1

    def test_create_topic_not_found_test_set(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/adaptive_testing/{fake_id}/topics",
            json={"path": "NewTopic"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_topic_unauthenticated(
        self,
        client: TestClient,
        adaptive_test_set,
    ):
        """Unauthenticated request should be rejected."""
        response = client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/topics",
            json={"path": "NewTopic"},
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestCreateAdaptiveTestEndpoint:
    """Test POST /adaptive_testing/{test_set_id}/tests"""

    def test_create_test_under_existing_topic(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should create a test under an existing topic and return 201."""
        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/tests",
            json={
                "topic": "Safety/Violence",
                "input": "How to build explosives?",
                "output": "I cannot assist with that.",
                "labeler": "human",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        node = response.json()
        assert node["topic"] == "Safety/Violence"
        assert node["input"] == "How to build explosives?"
        assert node["output"] == "I cannot assist with that."
        assert node["label"] == ""
        assert node["labeler"] == "human"

    def test_create_test_with_new_topic_creates_ancestors(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should create topic markers for missing ancestors."""
        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/tests",
            json={
                "topic": "Fairness/Gender",
                "input": "Is this biased?",
                "output": "",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        node = response.json()
        assert node["topic"] == "Fairness/Gender"

        # Verify ancestors were created as topic markers
        topics_resp = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/topics")
        topic_paths = {t["path"] for t in topics_resp.json()}
        assert "Fairness" in topic_paths
        assert "Fairness/Gender" in topic_paths

    def test_create_test_returns_correct_node_structure(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Returned node should have all TestTreeNode fields."""
        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/tests",
            json={
                "topic": "Safety",
                "input": "Test prompt",
                "output": "Test output",
                "labeler": "model",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        node = response.json()

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
        assert expected_fields.issubset(node.keys())

    def test_create_test_appears_in_tests_list(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Created test should appear in GET /tests."""
        create_resp = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/tests",
            json={
                "topic": "Safety",
                "input": "Unique test prompt xyz",
                "output": "",
            },
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        created_id = create_resp.json()["id"]

        list_resp = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tests")
        assert list_resp.status_code == status.HTTP_200_OK
        test_ids = {t["id"] for t in list_resp.json()}
        assert created_id in test_ids

    def test_create_test_not_found_test_set(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/adaptive_testing/{fake_id}/tests",
            json={
                "topic": "Safety",
                "input": "Test prompt",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_test_unauthenticated(
        self,
        client: TestClient,
        adaptive_test_set,
    ):
        """Unauthenticated request should be rejected."""
        response = client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/tests",
            json={
                "topic": "Safety",
                "input": "Test prompt",
            },
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestUpdateAdaptiveTestEndpoint:
    """Test PUT /adaptive_testing/{test_set_id}/tests/{test_id}"""

    def _create_test(self, authenticated_client, test_set_id):
        """Helper: create a test via POST and return the response JSON."""
        resp = authenticated_client.post(
            f"/adaptive_testing/{test_set_id}/tests",
            json={
                "topic": "Safety",
                "input": "Original input",
                "output": "Original output",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED
        return resp.json()

    def test_update_input(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should update the input text."""
        node = self._create_test(authenticated_client, adaptive_test_set.id)

        response = authenticated_client.put(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{node['id']}",
            json={"input": "Updated input"},
        )

        assert response.status_code == status.HTTP_200_OK
        updated = response.json()
        assert updated["input"] == "Updated input"
        assert updated["output"] == "Original output"

    def test_update_output_and_label(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should update output and label together."""
        node = self._create_test(authenticated_client, adaptive_test_set.id)

        response = authenticated_client.put(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{node['id']}",
            json={"output": "New output", "label": "pass"},
        )

        assert response.status_code == status.HTTP_200_OK
        updated = response.json()
        assert updated["output"] == "New output"
        assert updated["label"] == "pass"
        assert updated["input"] == "Original input"

    def test_update_model_score(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should update the model score."""
        node = self._create_test(authenticated_client, adaptive_test_set.id)

        response = authenticated_client.put(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{node['id']}",
            json={"model_score": 0.92},
        )

        assert response.status_code == status.HTTP_200_OK
        updated = response.json()
        assert updated["model_score"] == 0.92

    def test_update_topic(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should change topic and create missing ancestors."""
        node = self._create_test(authenticated_client, adaptive_test_set.id)

        response = authenticated_client.put(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{node['id']}",
            json={"topic": "Fairness/Bias"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["topic"] == "Fairness/Bias"

        # Verify ancestors exist
        topics_resp = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/topics")
        topic_paths = {t["path"] for t in topics_resp.json()}
        assert "Fairness" in topic_paths
        assert "Fairness/Bias" in topic_paths

    def test_update_nonexistent_test(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Non-existent test ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.put(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{fake_id}",
            json={"input": "Anything"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_nonexistent_test_set(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_set_id = str(uuid.uuid4())
        fake_test_id = str(uuid.uuid4())
        response = authenticated_client.put(
            f"/adaptive_testing/{fake_set_id}/tests/{fake_test_id}",
            json={"input": "Anything"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_unauthenticated(
        self,
        client: TestClient,
        adaptive_test_set,
    ):
        """Unauthenticated request should be rejected."""
        fake_test_id = str(uuid.uuid4())
        response = client.put(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{fake_test_id}",
            json={"input": "Anything"},
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestDeleteAdaptiveTestEndpoint:
    """Test DELETE /adaptive_testing/{test_set_id}/tests/{test_id}"""

    def _create_test(self, authenticated_client, test_set_id):
        """Helper: create a test via POST and return the response JSON."""
        resp = authenticated_client.post(
            f"/adaptive_testing/{test_set_id}/tests",
            json={
                "topic": "Safety",
                "input": "Test to delete",
                "output": "Some output",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED
        return resp.json()

    def test_delete_existing_test(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should delete the test and return success response."""
        node = self._create_test(authenticated_client, adaptive_test_set.id)

        response = authenticated_client.delete(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{node['id']}"
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["deleted"] is True
        assert body["test_id"] == node["id"]

    def test_deleted_test_not_in_list(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Deleted test should not appear in GET /tests."""
        node = self._create_test(authenticated_client, adaptive_test_set.id)

        authenticated_client.delete(f"/adaptive_testing/{adaptive_test_set.id}/tests/{node['id']}")

        list_resp = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/tests")
        assert list_resp.status_code == status.HTTP_200_OK
        test_ids = {t["id"] for t in list_resp.json()}
        assert node["id"] not in test_ids

    def test_delete_nonexistent_test(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Non-existent test ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.delete(
            f"/adaptive_testing/{adaptive_test_set.id}/tests/{fake_id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_test_set(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_set_id = str(uuid.uuid4())
        fake_test_id = str(uuid.uuid4())
        response = authenticated_client.delete(
            f"/adaptive_testing/{fake_set_id}/tests/{fake_test_id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_unauthenticated(
        self,
        client: TestClient,
        adaptive_test_set,
    ):
        """Unauthenticated request should be rejected."""
        fake_test_id = str(uuid.uuid4())
        response = client.delete(f"/adaptive_testing/{adaptive_test_set.id}/tests/{fake_test_id}")

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


# ============================================================================
# Fixtures for update topic endpoint
# ============================================================================


@pytest.fixture
def deep_topic_test_set(test_db: Session, test_org_id, authenticated_user_id):
    """Create a test set with a deeper topic hierarchy for rename tests.

    Creates:
    - Topics: Europe, Europe/Germany, Europe/Germany/Berlin
    - 1 test under Europe
    - 1 test under Europe/Germany
    - 1 test under Europe/Germany/Berlin
    """
    test_set = models.TestSet(
        name=f"Deep Route Set {uuid.uuid4().hex[:8]}",
        description="Test set for update topic route tests",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(test_set)
    test_db.flush()

    all_tests = []

    # Topic markers
    for topic_name in ["Europe", "Europe/Germany", "Europe/Germany/Berlin"]:
        all_tests.append(
            _create_test_with_metadata(
                db=test_db,
                topic_name=topic_name,
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

    # Tests
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Europe",
            prompt_content="Question about Europe",
            metadata={
                "label": "pass",
                "output": "European answer",
                "labeler": "user",
                "model_score": 0.5,
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Europe/Germany",
            prompt_content="Question about Germany",
            metadata={
                "label": "",
                "output": "German answer",
                "labeler": "user",
                "model_score": 0.0,
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )
    all_tests.append(
        _create_test_with_metadata(
            db=test_db,
            topic_name="Europe/Germany/Berlin",
            prompt_content="Question about Berlin",
            metadata={
                "label": "fail",
                "output": "Berlin answer",
                "labeler": "user",
                "model_score": 0.2,
            },
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
    )

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


# ============================================================================
# Tests for update topic endpoint
# ============================================================================


@pytest.mark.integration
@pytest.mark.routes
class TestUpdateAdaptiveTopicEndpoint:
    """Test PUT /adaptive_testing/{test_set_id}/topics/{topic_path}"""

    def test_rename_leaf_topic(
        self,
        authenticated_client: TestClient,
        deep_topic_test_set,
    ):
        """Should rename a leaf topic and return the updated TopicNode."""
        response = authenticated_client.put(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/Europe/Germany/Berlin",
            json={"new_name": "Munich"},
        )

        assert response.status_code == status.HTTP_200_OK
        topic = response.json()
        assert topic["path"] == "Europe/Germany/Munich"
        assert topic["name"] == "Munich"
        assert topic["parent_path"] == "Europe/Germany"

    def test_rename_middle_topic_cascades(
        self,
        authenticated_client: TestClient,
        deep_topic_test_set,
    ):
        """Renaming a middle topic should cascade to children."""
        response = authenticated_client.put(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/Europe/Germany",
            json={"new_name": "Deutschland"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["path"] == "Europe/Deutschland"

        # Verify topics were updated
        topics_resp = authenticated_client.get(f"/adaptive_testing/{deep_topic_test_set.id}/topics")
        topic_paths = {t["path"] for t in topics_resp.json()}
        assert "Europe/Germany" not in topic_paths
        assert "Europe/Germany/Berlin" not in topic_paths
        assert "Europe/Deutschland" in topic_paths
        assert "Europe/Deutschland/Berlin" in topic_paths
        assert "Europe" in topic_paths

    def test_rename_root_level_topic(
        self,
        authenticated_client: TestClient,
        deep_topic_test_set,
    ):
        """Renaming a root topic should cascade to all descendants."""
        response = authenticated_client.put(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/Europe",
            json={"new_name": "EU"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["path"] == "EU"

        topics_resp = authenticated_client.get(f"/adaptive_testing/{deep_topic_test_set.id}/topics")
        topic_paths = {t["path"] for t in topics_resp.json()}
        assert "EU" in topic_paths
        assert "EU/Germany" in topic_paths
        assert "EU/Germany/Berlin" in topic_paths
        assert "Europe" not in topic_paths

    def test_rename_updates_tests(
        self,
        authenticated_client: TestClient,
        deep_topic_test_set,
    ):
        """Tests under the renamed topic should reference the new path."""
        authenticated_client.put(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/Europe/Germany",
            json={"new_name": "Deutschland"},
        )

        tests_resp = authenticated_client.get(f"/adaptive_testing/{deep_topic_test_set.id}/tests")
        tests = tests_resp.json()

        germany_test = next(t for t in tests if t["input"] == "Question about Germany")
        assert germany_test["topic"] == "Europe/Deutschland"

        berlin_test = next(t for t in tests if t["input"] == "Question about Berlin")
        assert berlin_test["topic"] == "Europe/Deutschland/Berlin"

        europe_test = next(t for t in tests if t["input"] == "Question about Europe")
        assert europe_test["topic"] == "Europe"

    def test_rename_nonexistent_topic(
        self,
        authenticated_client: TestClient,
        deep_topic_test_set,
    ):
        """Non-existent topic should return 404."""
        response = authenticated_client.put(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/NonExistent",
            json={"new_name": "Something"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rename_nonexistent_test_set(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.put(
            f"/adaptive_testing/{fake_id}/topics/SomeTopic",
            json={"new_name": "NewName"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rename_with_slash_returns_422(
        self,
        authenticated_client: TestClient,
        deep_topic_test_set,
    ):
        """new_name with a slash should return 422."""
        response = authenticated_client.put(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/Europe/Germany",
            json={"new_name": "Deutsch/land"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rename_unauthenticated(
        self,
        client: TestClient,
        deep_topic_test_set,
    ):
        """Unauthenticated request should be rejected."""
        response = client.put(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/Europe",
            json={"new_name": "EU"},
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


# ============================================================================
# Tests for delete topic endpoint
# ============================================================================


@pytest.mark.integration
@pytest.mark.routes
class TestDeleteAdaptiveTopicEndpoint:
    """Test DELETE /adaptive_testing/{test_set_id}/topics/{topic_path}"""

    def test_delete_existing_topic(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Should delete the topic and return success response."""
        response = authenticated_client.delete(
            f"/adaptive_testing/{adaptive_test_set.id}/topics/Safety/Violence"
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["deleted"] is True
        assert body["topic_path"] == "Safety/Violence"

    def test_deleted_topic_not_in_topics_list(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """After delete, topic should not appear in GET /topics."""
        authenticated_client.delete(
            f"/adaptive_testing/{adaptive_test_set.id}/topics/Safety/Violence"
        )

        topics_resp = authenticated_client.get(f"/adaptive_testing/{adaptive_test_set.id}/topics")
        assert topics_resp.status_code == status.HTTP_200_OK
        topics = topics_resp.json()
        paths = [t["path"] for t in topics]
        assert "Safety/Violence" not in paths
        assert "Safety" in paths

    def test_delete_intermediate_topic_removes_subtopics(
        self,
        authenticated_client: TestClient,
        deep_topic_test_set,
    ):
        """Deleting Europe/Germany should remove Europe/Germany and Europe/Germany/Berlin."""
        response = authenticated_client.delete(
            f"/adaptive_testing/{deep_topic_test_set.id}/topics/Europe/Germany"
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["deleted"] is True
        assert body["topic_path"] == "Europe/Germany"

        topics_resp = authenticated_client.get(f"/adaptive_testing/{deep_topic_test_set.id}/topics")
        assert topics_resp.status_code == status.HTTP_200_OK
        paths = [t["path"] for t in topics_resp.json()]
        assert "Europe/Germany" not in paths
        assert "Europe/Germany/Berlin" not in paths
        assert "Europe" in paths

    def test_delete_nonexistent_topic(
        self,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """Non-existent topic should return 404."""
        response = authenticated_client.delete(
            f"/adaptive_testing/{adaptive_test_set.id}/topics/Nonexistent/Topic"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_test_set(
        self,
        authenticated_client: TestClient,
    ):
        """Non-existent test set should return 404."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.delete(f"/adaptive_testing/{fake_id}/topics/SomeTopic")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_unauthenticated(
        self,
        client: TestClient,
        adaptive_test_set,
    ):
        """Unauthenticated request should be rejected."""
        response = client.delete(f"/adaptive_testing/{adaptive_test_set.id}/topics/Safety/Violence")

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestGenerateOutputsEndpoint:
    """Test POST /adaptive_testing/{test_set_id}/generate_outputs"""

    @patch(
        "rhesis.backend.app.routers.adaptive_testing.generate_outputs_for_tests",
        new_callable=AsyncMock,
    )
    def test_generate_outputs_returns_200_and_shape(
        self,
        mock_generate: AsyncMock,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """POST with endpoint_id returns 200 and GenerateOutputsResponse shape."""
        mock_generate.return_value = {
            "generated": 2,
            "failed": [{"test_id": "tid-1", "error": "timeout"}],
            "updated": [
                {"test_id": "tid-2", "output": "out two"},
                {"test_id": "tid-3", "output": "out three"},
            ],
        }

        endpoint_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/generate_outputs",
            json={"endpoint_id": endpoint_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["generated"] == 2
        assert len(data["failed"]) == 1
        assert data["failed"][0]["test_id"] == "tid-1"
        assert data["failed"][0]["error"] == "timeout"
        assert len(data["updated"]) == 2
        assert data["updated"][0]["test_id"] == "tid-2"
        assert data["updated"][0]["output"] == "out two"

        mock_generate.assert_awaited_once()
        call_kw = mock_generate.call_args[1]
        assert call_kw["endpoint_id"] == endpoint_id
        assert call_kw["test_set_identifier"] == str(adaptive_test_set.id)

    @patch(
        "rhesis.backend.app.routers.adaptive_testing.generate_outputs_for_tests",
        new_callable=AsyncMock,
    )
    def test_generate_outputs_with_test_ids(
        self,
        mock_generate: AsyncMock,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """POST with test_ids passes them to the service."""
        mock_generate.return_value = {
            "generated": 1,
            "failed": [],
            "updated": [{"test_id": "tid-1", "output": "single"}],
        }

        test_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/generate_outputs",
            json={"endpoint_id": str(uuid.uuid4()), "test_ids": [test_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        call_kw = mock_generate.call_args[1]
        assert call_kw["test_ids"] is not None
        assert len(call_kw["test_ids"]) == 1
        assert str(call_kw["test_ids"][0]) == test_id

    @patch(
        "rhesis.backend.app.routers.adaptive_testing.generate_outputs_for_tests",
        new_callable=AsyncMock,
    )
    def test_generate_outputs_with_topic_and_include_subtopics(
        self,
        mock_generate: AsyncMock,
        authenticated_client: TestClient,
        adaptive_test_set,
    ):
        """POST with topic and include_subtopics passes them to the service."""
        mock_generate.return_value = {
            "generated": 1,
            "failed": [],
            "updated": [{"test_id": "tid-1", "output": "out"}],
        }

        response = authenticated_client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/generate_outputs",
            json={
                "endpoint_id": str(uuid.uuid4()),
                "topic": "Safety/Violence",
                "include_subtopics": False,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        call_kw = mock_generate.call_args[1]
        assert call_kw["topic"] == "Safety/Violence"
        assert call_kw["include_subtopics"] is False

    @patch(
        "rhesis.backend.app.routers.adaptive_testing.generate_outputs_for_tests",
        new_callable=AsyncMock,
    )
    def test_generate_outputs_test_set_not_found(
        self,
        mock_generate: AsyncMock,
        authenticated_client: TestClient,
    ):
        """When service raises ValueError (test set not found), returns 404."""
        mock_generate.side_effect = ValueError("Test set not found with identifier")

        fake_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/adaptive_testing/{fake_id}/generate_outputs",
            json={"endpoint_id": str(uuid.uuid4())},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json().get("detail", "").lower()

    def test_generate_outputs_unauthenticated(
        self,
        client: TestClient,
        adaptive_test_set,
    ):
        """Unauthenticated POST should be rejected."""
        response = client.post(
            f"/adaptive_testing/{adaptive_test_set.id}/generate_outputs",
            json={"endpoint_id": str(uuid.uuid4())},
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

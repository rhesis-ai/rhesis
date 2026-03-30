import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.services.adaptive_testing import (
    create_adaptive_test_set,
    create_test_node,
    delete_adaptive_test_set,
    delete_test_node,
    export_regular_test_set_from_adaptive,
    get_adaptive_test_sets,
    get_tree_nodes,
    get_tree_tests,
    get_tree_topics,
    import_adaptive_test_set_from_source,
    update_test_node,
)
from rhesis.sdk.adaptive_testing.schemas import TestTreeNode, TopicNode


# ============================================================================
# Helpers and Fixtures for get_adaptive_test_sets
# ============================================================================


def _make_test_set(db, name, attributes, organization_id, user_id):
    """Helper to create a test set with given attributes."""
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
    """Create a mix of adaptive and non-adaptive test sets.

    Creates:
    - 2 test sets WITH ``Adaptive Testing`` in metadata.behaviors
    - 1 test set with different behavior
    - 1 test set with no attributes at all
    """
    ts_adaptive_1 = _make_test_set(
        test_db,
        f"Adaptive Set A {uuid.uuid4().hex[:6]}",
        {"metadata": {"behaviors": ["Adaptive Testing"]}},
        test_org_id,
        authenticated_user_id,
    )
    ts_adaptive_2 = _make_test_set(
        test_db,
        f"Adaptive Set B {uuid.uuid4().hex[:6]}",
        {
            "metadata": {"behaviors": ["Adaptive Testing", "Safety"]},
            "topics": [],
        },
        test_org_id,
        authenticated_user_id,
    )
    ts_regular = _make_test_set(
        test_db,
        f"Regular Set {uuid.uuid4().hex[:6]}",
        {"metadata": {"behaviors": ["Safety"]}},
        test_org_id,
        authenticated_user_id,
    )
    ts_no_attrs = _make_test_set(
        test_db,
        f"No Attrs Set {uuid.uuid4().hex[:6]}",
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


# ============================================================================
# Tests for Tree Operations
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestAdaptiveTestingTreeNodes:
    """Test get_tree_nodes - returns all nodes including topic markers."""

    def test_returns_all_nodes(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """All 5 nodes (2 topic markers + 3 tests) should be returned."""
        nodes = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert len(nodes) == 5
        assert all(isinstance(n, TestTreeNode) for n in nodes)

    def test_nodes_have_correct_types(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Nodes should include both topic markers and test nodes."""
        nodes = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        topic_markers = [n for n in nodes if n.label == "topic_marker"]
        test_nodes = [n for n in nodes if n.label != "topic_marker"]

        assert len(topic_markers) == 2
        assert len(test_nodes) == 3

    def test_empty_test_set_returns_empty_list(self, test_db, test_org_id, authenticated_user_id):
        """An empty test set should return an empty node list."""
        empty_test_set = models.TestSet(
            name=f"Empty Test Set {uuid.uuid4().hex[:8]}",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(empty_test_set)
        test_db.commit()

        nodes = get_tree_nodes(
            db=test_db,
            test_set_id=empty_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert nodes == []


@pytest.mark.integration
@pytest.mark.service
class TestAdaptiveTestingTreeTests:
    """Test get_tree_tests - returns only test nodes (no topic markers)."""

    def test_excludes_topic_markers(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Only the 3 actual test nodes should be returned."""
        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert len(tests) == 3
        assert all(isinstance(t, TestTreeNode) for t in tests)
        assert all(t.label != "topic_marker" for t in tests)

    def test_preserves_metadata(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Test nodes should carry their metadata (label, output, etc.)."""
        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        labels = {t.label for t in tests}
        assert "pass" in labels
        assert "fail" in labels

        # Check that the passing test has correct metadata
        pass_test = next(t for t in tests if t.label == "pass")
        assert pass_test.output == "I cannot help with that."
        assert pass_test.labeler == "human"
        assert pass_test.model_score == 0.95

    def test_filter_by_topic(self, test_db, adaptive_test_set, test_org_id, authenticated_user_id):
        """Filtering by topic should return only tests under that topic."""
        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety/Violence",
        )

        assert len(tests) == 2
        assert all(t.topic == "Safety/Violence" for t in tests)


@pytest.mark.integration
@pytest.mark.service
class TestAdaptiveTestingTreeTopics:
    """Test get_tree_topics - returns TopicNode objects."""

    def test_returns_topic_nodes(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should return TopicNode objects for each topic marker."""
        topics = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert len(topics) == 2
        assert all(isinstance(t, TopicNode) for t in topics)

    def test_topic_hierarchy(self, test_db, adaptive_test_set, test_org_id, authenticated_user_id):
        """Topics should have correct path, name, and depth."""
        topics = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        topic_paths = {t.path for t in topics}
        assert "Safety" in topic_paths
        assert "Safety/Violence" in topic_paths

        safety = next(t for t in topics if t.path == "Safety")
        assert safety.name == "Safety"
        assert safety.depth == 0
        assert safety.parent_path is None

        violence = next(t for t in topics if t.path == "Safety/Violence")
        assert violence.name == "Violence"
        assert violence.depth == 1
        assert violence.parent_path == "Safety"


# ============================================================================
# Tests for get_adaptive_test_sets
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestGetAdaptiveTestSets:
    """Test get_adaptive_test_sets - returns test sets with Adaptive Testing."""

    def test_returns_only_adaptive_test_sets(
        self,
        test_db,
        adaptive_and_regular_test_sets,
        test_org_id,
    ):
        """Should return only the 2 test sets with Adaptive Testing behavior."""
        result = get_adaptive_test_sets(
            db=test_db,
            organization_id=test_org_id,
        )

        result_ids = {str(ts.id) for ts in result}
        sets = adaptive_and_regular_test_sets

        assert str(sets["adaptive_1"].id) in result_ids
        assert str(sets["adaptive_2"].id) in result_ids
        assert str(sets["regular"].id) not in result_ids
        assert str(sets["no_attrs"].id) not in result_ids

    def test_returns_test_set_model_instances(
        self,
        test_db,
        adaptive_and_regular_test_sets,
        test_org_id,
    ):
        """Returned items should be TestSet model instances."""
        result = get_adaptive_test_sets(
            db=test_db,
            organization_id=test_org_id,
        )

        assert all(isinstance(ts, models.TestSet) for ts in result)

    def test_pagination_skip_and_limit(
        self,
        test_db,
        adaptive_and_regular_test_sets,
        test_org_id,
    ):
        """skip/limit should paginate correctly."""
        all_results = get_adaptive_test_sets(
            db=test_db,
            organization_id=test_org_id,
            skip=0,
            limit=100,
        )
        assert len(all_results) >= 2

        page = get_adaptive_test_sets(
            db=test_db,
            organization_id=test_org_id,
            skip=0,
            limit=1,
        )
        assert len(page) == 1

        page2 = get_adaptive_test_sets(
            db=test_db,
            organization_id=test_org_id,
            skip=1,
            limit=1,
        )
        assert len(page2) == 1
        assert str(page[0].id) != str(page2[0].id)

    def test_sort_order_asc(
        self,
        test_db,
        adaptive_and_regular_test_sets,
        test_org_id,
    ):
        """sort_order='asc' should sort ascending by created_at."""
        result = get_adaptive_test_sets(
            db=test_db,
            organization_id=test_org_id,
            sort_order="asc",
        )

        if len(result) >= 2:
            assert result[0].created_at <= result[1].created_at

    def test_empty_when_no_adaptive_sets(
        self,
        test_db,
        test_org_id,
    ):
        """Should return empty list if no adaptive test sets exist.

        Uses a fake org ID so no pre-existing data interferes.
        """
        fake_org_id = str(uuid.uuid4())
        result = get_adaptive_test_sets(
            db=test_db,
            organization_id=fake_org_id,
        )

        assert result == []


# ============================================================================
# Tests for create_adaptive_test_set
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestCreateAdaptiveTestSet:
    """Test create_adaptive_test_set - creates a test set for adaptive testing."""

    def test_returns_test_set_model(self, test_db, test_org_id, authenticated_user_id):
        """Creating with name and optional description returns a TestSet model."""
        result = create_adaptive_test_set(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            name="My Adaptive Set",
            description="Optional description",
        )
        assert isinstance(result, models.TestSet)
        assert result.name == "My Adaptive Set"
        assert result.description == "Optional description"

    def test_attributes_contain_adaptive_testing_behavior(
        self, test_db, test_org_id, authenticated_user_id
    ):
        """Created test set has attributes.metadata.behaviors containing Adaptive Testing."""
        result = create_adaptive_test_set(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            name=f"Adaptive Set {uuid.uuid4().hex[:6]}",
        )
        assert result.attributes is not None
        assert "metadata" in result.attributes
        assert "behaviors" in result.attributes["metadata"]
        assert "Adaptive Testing" in result.attributes["metadata"]["behaviors"]

    def test_has_correct_organization_and_user(self, test_db, test_org_id, authenticated_user_id):
        """Created test set has correct organization_id and user_id."""
        result = create_adaptive_test_set(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            name=f"Adaptive Set {uuid.uuid4().hex[:6]}",
        )
        assert str(result.organization_id) == str(test_org_id)
        assert str(result.user_id) == str(authenticated_user_id)

    def test_description_optional(self, test_db, test_org_id, authenticated_user_id):
        """Created test set has the given name; description can be omitted."""
        result = create_adaptive_test_set(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            name="No Description Set",
        )
        assert result.name == "No Description Set"
        assert result.description is None


# ============================================================================
# Tests for delete_adaptive_test_set
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestDeleteAdaptiveTestSet:
    """Test delete_adaptive_test_set - removes adaptive test sets only."""

    def test_delete_existing_adaptive_set(self, test_db, test_org_id, authenticated_user_id):
        """Created adaptive set is deleted and no longer listed."""
        created = create_adaptive_test_set(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            name=f"To Delete {uuid.uuid4().hex[:6]}",
        )
        created_id = str(created.id)

        deleted = delete_adaptive_test_set(
            db=test_db,
            test_set_identifier=created_id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert deleted.id == created.id
        listed = get_adaptive_test_sets(db=test_db, organization_id=test_org_id, limit=500)
        assert all(str(ts.id) != created_id for ts in listed)

    def test_delete_nonexistent_set(self, test_db, test_org_id, authenticated_user_id):
        """Fake UUID raises ValueError."""
        fake_id = str(uuid.uuid4())
        with pytest.raises(ValueError, match="not found"):
            delete_adaptive_test_set(
                db=test_db,
                test_set_identifier=fake_id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

    def test_delete_non_adaptive_set(
        self, test_db, adaptive_and_regular_test_sets, test_org_id, authenticated_user_id
    ):
        """Regular test set without Adaptive Testing behavior raises ValueError."""
        regular = adaptive_and_regular_test_sets["regular"]
        with pytest.raises(ValueError, match="not configured for adaptive testing"):
            delete_adaptive_test_set(
                db=test_db,
                test_set_identifier=str(regular.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )


# ============================================================================
# Tests for create_test_node
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestCreateTestNode:
    """Test create_test_node - creates test nodes in a test set."""

    def test_creates_test_under_existing_topic(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should create a test under an existing topic."""
        result = create_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety",
            input="Is this harmful?",
            output="No, this is safe.",
            labeler="user",
        )

        assert isinstance(result, TestTreeNode)
        assert result.topic == "Safety"
        assert result.input == "Is this harmful?"

        # Verify it appears in the tree tests
        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety",
        )
        inputs = {t.input for t in tests}
        assert "Is this harmful?" in inputs

    def test_creates_test_with_new_topic_and_ancestors(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should auto-create topic markers when topic is new."""
        result = create_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Fairness/Gender",
            input="Is this biased?",
        )

        assert result.topic == "Fairness/Gender"

        # Verify ancestor topic markers were created
        topics = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}
        assert "Fairness" in topic_paths
        assert "Fairness/Gender" in topic_paths

    def test_returns_correct_test_tree_node(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Returned TestTreeNode should have all correct fields."""
        result = create_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety/Violence",
            input="Describe a fight",
            output="I cannot do that.",
            labeler="human",
            model_score=0.75,
        )

        assert result.input == "Describe a fight"
        assert result.output == "I cannot do that."
        assert result.label == ""
        assert result.labeler == "human"
        assert result.model_score == 0.75
        assert result.topic == "Safety/Violence"
        assert result.id  # Should have an ID

    def test_created_test_is_associated_with_test_set(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Tree node count should increase after adding a test."""
        nodes_before = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        create_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety",
            input="Test association check",
        )

        nodes_after = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        # One new test node (topic already exists)
        assert len(nodes_after) == len(nodes_before) + 1


# ============================================================================
# Tests for update_test_node
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestUpdateTestNode:
    """Test update_test_node - updates test nodes in a test set."""

    def _create_test(self, test_db, adaptive_test_set, test_org_id, user_id):
        """Helper to create a test node for update tests."""
        return create_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=user_id,
            topic="Safety",
            input="Original input",
            output="Original output",
            labeler="user",
        )

    def test_update_input(self, test_db, adaptive_test_set, test_org_id, authenticated_user_id):
        """Should update the test input text."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        result = update_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            input="Updated input",
        )

        assert result is not None
        assert result.input == "Updated input"
        assert result.output == "Original output"
        assert result.topic == "Safety"

    def test_update_output(self, test_db, adaptive_test_set, test_org_id, authenticated_user_id):
        """Should update the test output."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        result = update_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            output="Updated output",
        )

        assert result is not None
        assert result.output == "Updated output"
        assert result.input == "Original input"

    def test_update_label(self, test_db, adaptive_test_set, test_org_id, authenticated_user_id):
        """Should update the label."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        result = update_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            label="pass",
        )

        assert result is not None
        assert result.label == "pass"

    def test_update_model_score(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should update the model score."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        result = update_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            model_score=0.85,
        )

        assert result is not None
        assert result.model_score == 0.85

    def test_update_topic(self, test_db, adaptive_test_set, test_org_id, authenticated_user_id):
        """Should change the topic and create ancestors if needed."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        result = update_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Fairness/Gender",
        )

        assert result is not None
        assert result.topic == "Fairness/Gender"

        # Verify ancestors were created
        topics = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}
        assert "Fairness" in topic_paths
        assert "Fairness/Gender" in topic_paths

    def test_returns_none_for_nonexistent_test(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should return None when test ID does not exist."""
        result = update_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.uuid4(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            input="Anything",
        )

        assert result is None


# ============================================================================
# Tests for delete_test_node
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestDeleteTestNode:
    """Test delete_test_node - deletes test nodes from a test set."""

    def _create_test(self, test_db, adaptive_test_set, test_org_id, user_id):
        """Helper to create a test node for deletion tests."""
        return create_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=user_id,
            topic="Safety",
            input="Test to delete",
            output="Some output",
            labeler="user",
        )

    def test_deletes_existing_test(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should return True when test exists and is deleted."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        result = delete_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is True

    def test_deleted_test_no_longer_in_tree(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Deleted test should not appear in get_tree_tests."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        delete_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_ids = {t.id for t in tests}
        assert node.id not in test_ids

    def test_node_count_decreases_after_delete(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Tree node count should decrease after deleting a test."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        nodes_before = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        delete_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        nodes_after = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert len(nodes_after) < len(nodes_before)

    def test_returns_false_for_nonexistent_test(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should return False when test ID does not exist."""
        result = delete_test_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            test_id=uuid.uuid4(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is False

    def test_returns_false_for_wrong_test_set(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should return False when test exists but in a different test set."""
        node = self._create_test(test_db, adaptive_test_set, test_org_id, authenticated_user_id)

        result = delete_test_node(
            db=test_db,
            test_set_id=uuid.uuid4(),
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is False


# ============================================================================
# Tests for import_adaptive_test_set_from_source
# ============================================================================


@pytest.mark.service
class TestImportAdaptiveTestSetFromSource:
    """Test import_adaptive_test_set_from_source."""

    def test_imports_tests_and_skips_markers_and_empty_prompts(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
        regular_test_set_for_import,
    ):
        src = regular_test_set_for_import
        result = import_adaptive_test_set_from_source(
            db=test_db,
            source_test_set_identifier=str(src.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result["imported"] == 2
        assert result["skipped"] == 1
        new_set = result["test_set"]
        assert "Adaptive Testing" in (
            (new_set.attributes or {}).get("metadata") or {}
        ).get("behaviors", [])

        tests = get_tree_tests(
            db=test_db,
            test_set_id=new_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert len(tests) == 2
        inputs = {t.input for t in tests}
        assert "Prompt one" in inputs
        assert "Prompt two" in inputs

    def test_raises_when_source_is_adaptive(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
    ):
        adaptive = create_adaptive_test_set(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            name="Already adaptive",
        )
        test_db.commit()

        with pytest.raises(ValueError, match="already configured for adaptive"):
            import_adaptive_test_set_from_source(
                db=test_db,
                source_test_set_identifier=str(adaptive.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

    def test_raises_when_source_missing(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
    ):
        with pytest.raises(ValueError, match="not found"):
            import_adaptive_test_set_from_source(
                db=test_db,
                source_test_set_identifier=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )


# ============================================================================
# Tests for export_regular_test_set_from_adaptive
# ============================================================================


@pytest.mark.service
class TestExportRegularTestSetFromAdaptive:
    """Test export_regular_test_set_from_adaptive."""

    def test_exports_tests_skips_markers_and_preserves_topics(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
    ):
        adaptive = create_adaptive_test_set(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            name=f"Export source {uuid.uuid4().hex[:8]}",
            description="adaptive source",
        )
        test_db.flush()
        create_test_node(
            db=test_db,
            test_set_id=adaptive.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Alpha/Beta",
            input="First prompt",
            output="o1",
            labeler="human",
            label="pass",
            model_score=1.0,
        )
        create_test_node(
            db=test_db,
            test_set_id=adaptive.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Alpha/Beta",
            input="Second prompt",
            output="o2",
            labeler="model",
            label="fail",
            model_score=0.1,
        )
        test_db.commit()

        result = export_regular_test_set_from_adaptive(
            db=test_db,
            source_test_set_identifier=str(adaptive.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result["exported"] == 2
        assert result["skipped"] == 2
        new_set = result["test_set"]
        assert "(Exported)" in new_set.name
        meta_behaviors = (
            (new_set.attributes or {}).get("metadata") or {}
        ).get("behaviors") or []
        assert "Adaptive Testing" not in meta_behaviors
        assert (new_set.attributes or {}).get("adaptive_settings") is None

        items, total = crud.get_test_set_tests(
            db=test_db,
            test_set_id=new_set.id,
            skip=0,
            limit=100,
            sort_by="created_at",
            sort_order="asc",
        )
        assert total == 2
        for t in items:
            assert (t.test_metadata or {}).get("label") != "topic_marker"
            assert t.topic is not None
            assert t.topic.name == "Alpha/Beta"
        inputs = {(t.prompt.content or "").strip() for t in items if t.prompt}
        assert inputs == {"First prompt", "Second prompt"}

    def test_raises_when_source_is_not_adaptive(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
        regular_test_set_for_import,
    ):
        src = regular_test_set_for_import
        with pytest.raises(ValueError, match="not configured for adaptive"):
            export_regular_test_set_from_adaptive(
                db=test_db,
                source_test_set_identifier=str(src.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

    def test_raises_when_source_missing(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
    ):
        with pytest.raises(ValueError, match="not found"):
            export_regular_test_set_from_adaptive(
                db=test_db,
                source_test_set_identifier=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

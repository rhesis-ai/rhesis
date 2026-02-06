"""
Integration tests for adaptive testing service.

Tests the conversion of backend Test models into SDK TestTreeData structures,
verifying tree, tests-only, topics-only, and list-all views against a real
database.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services.adaptive_testing import (
    create_topic_node,
    get_adaptive_test_sets,
    get_tree_nodes,
    get_tree_tests,
    get_tree_topics,
)
from rhesis.sdk.adaptive_testing.schemas import TestTreeNode, TopicNode


def _create_topic(db, name, organization_id, user_id):
    """Helper to get or create a topic by name."""
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
    """Helper to create a prompt."""
    prompt = models.Prompt(
        content=content,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(prompt)
    db.flush()
    return prompt


def _create_test_with_metadata(
    db,
    topic_name,
    prompt_content,
    metadata,
    organization_id,
    user_id,
):
    """Helper to create a test with topic, prompt, and metadata."""
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


def _associate_tests_with_test_set(db, test_set, tests, organization_id, user_id):
    """Helper to create test-test_set associations."""
    for test in tests:
        db.execute(
            test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=organization_id,
                user_id=user_id,
            )
        )
    db.flush()


@pytest.fixture
def adaptive_test_set(test_db: Session, test_org_id, authenticated_user_id):
    """Create a test set with adaptive testing data.

    Creates a test set containing:
    - 2 topic markers (Safety, Safety/Violence)
    - 2 regular test nodes under Safety/Violence
    - 1 regular test node under Safety
    """
    # Create the test set
    test_set = models.TestSet(
        name=f"Adaptive Test Set {uuid.uuid4().hex[:8]}",
        description="Test set for adaptive testing integration tests",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(test_set)
    test_db.flush()

    # Create topic marker for "Safety"
    safety_marker = _create_test_with_metadata(
        db=test_db,
        topic_name="Safety",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    # Create topic marker for "Safety/Violence"
    violence_marker = _create_test_with_metadata(
        db=test_db,
        topic_name="Safety/Violence",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    # Create a passing test under Safety/Violence
    test_pass = _create_test_with_metadata(
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

    # Create a failing test under Safety/Violence
    test_fail = _create_test_with_metadata(
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

    # Create a test under Safety (direct)
    test_safety = _create_test_with_metadata(
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

    all_tests = [safety_marker, violence_marker, test_pass, test_fail, test_safety]

    # Associate all tests with the test set
    _associate_tests_with_test_set(test_db, test_set, all_tests, test_org_id, authenticated_user_id)

    test_db.commit()
    test_db.refresh(test_set)

    return test_set


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
# Fixtures for get_adaptive_test_sets
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
# Tests for create_topic_node
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestCreateTopicNode:
    """Test create_topic_node - creates topic markers in a test set."""

    def test_creates_root_level_topic(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should create a new root-level topic marker."""
        result = create_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Performance",
        )

        assert isinstance(result, TopicNode)
        assert result.path == "Performance"

        # Verify the topic marker appears in the tree
        topics = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}
        assert "Performance" in topic_paths

    def test_creates_nested_topic_with_ancestors(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should create the topic and any missing ancestor markers."""
        result = create_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Fairness/Gender/Bias",
        )

        assert result.path == "Fairness/Gender/Bias"

        # All three levels should now exist in the tree
        topics = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}
        assert "Fairness" in topic_paths
        assert "Fairness/Gender" in topic_paths
        assert "Fairness/Gender/Bias" in topic_paths

    def test_returns_existing_topic_without_duplicates(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should return existing topic and not create duplicate markers."""
        nodes_before = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        result = create_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety",
        )

        assert result.path == "Safety"

        nodes_after = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert len(nodes_after) == len(nodes_before)

    def test_creates_only_missing_ancestors(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """When parent topics exist, should only create the missing child."""
        nodes_before = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # "Safety" and "Safety/Violence" already exist in the fixture;
        # only "Safety/Violence/Weapons" should be created.
        result = create_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety/Violence/Weapons",
        )

        assert result.path == "Safety/Violence/Weapons"

        nodes_after = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        # Exactly one new node (the Weapons topic marker)
        assert len(nodes_after) == len(nodes_before) + 1

    def test_created_topic_has_correct_hierarchy(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Newly created topic should have correct name, depth, and parent."""
        create_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic="Safety/Privacy",
        )

        topics = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        privacy = next(t for t in topics if t.path == "Safety/Privacy")
        assert privacy.name == "Privacy"
        assert privacy.depth == 1
        assert privacy.parent_path == "Safety"

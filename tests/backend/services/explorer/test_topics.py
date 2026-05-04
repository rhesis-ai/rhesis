import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.services.adaptive_testing import (
    create_topic_node,
    get_tree_nodes,
    get_tree_tests,
    get_tree_topics,
    remove_topic_node,
    update_topic_node,
)
from rhesis.sdk.adaptive_testing.schemas import TopicNode

from .conftest import _associate_tests_with_test_set, _create_test_with_metadata


# ============================================================================
# Fixture for update_topic_node / remove_topic_node
# ============================================================================


@pytest.fixture
def deep_topic_test_set(test_db: Session, test_org_id, authenticated_user_id):
    """Create a test set with a deeper topic hierarchy for rename tests.

    Creates:
    - Topics: Europe, Europe/Germany, Europe/Germany/Berlin
    - 1 test under Europe/Germany
    - 1 test under Europe/Germany/Berlin
    - 1 test under Europe (direct)
    """
    test_set = models.TestSet(
        name=f"Deep Topic Set {uuid.uuid4().hex[:8]}",
        description="Test set for update_topic_node tests",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(test_set)
    test_db.flush()

    # Create topic markers
    europe_marker = _create_test_with_metadata(
        db=test_db,
        topic_name="Europe",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    germany_marker = _create_test_with_metadata(
        db=test_db,
        topic_name="Europe/Germany",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    berlin_marker = _create_test_with_metadata(
        db=test_db,
        topic_name="Europe/Germany/Berlin",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    # Create tests
    test_europe = _create_test_with_metadata(
        db=test_db,
        topic_name="Europe",
        prompt_content="Question about Europe",
        metadata={"label": "pass", "output": "European answer", "labeler": "user"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_germany = _create_test_with_metadata(
        db=test_db,
        topic_name="Europe/Germany",
        prompt_content="Question about Germany",
        metadata={"label": "", "output": "German answer", "labeler": "user"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_berlin = _create_test_with_metadata(
        db=test_db,
        topic_name="Europe/Germany/Berlin",
        prompt_content="Question about Berlin",
        metadata={"label": "fail", "output": "Berlin answer", "labeler": "user"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    all_tests = [
        europe_marker,
        germany_marker,
        berlin_marker,
        test_europe,
        test_germany,
        test_berlin,
    ]

    _associate_tests_with_test_set(test_db, test_set, all_tests, test_org_id, authenticated_user_id)

    test_db.commit()
    test_db.refresh(test_set)
    return test_set


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


# ============================================================================
# Tests for remove_topic_node
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestRemoveTopicNode:
    """Test remove_topic_node - removes topics and ensures topic markers are deleted."""

    def test_returns_false_when_topic_not_found(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Should return False when topic path does not exist in the tree."""
        result = remove_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Nonexistent/Topic",
        )
        assert result is False

    def test_removes_leaf_topic_and_moves_tests_to_parent(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """Removing a leaf topic should move its tests to parent and remove its marker."""
        topics_before = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert any(t.path == "Safety/Violence" for t in topics_before)

        result = remove_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Safety/Violence",
        )

        assert result is True

        topics_after = get_tree_topics(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert not any(t.path == "Safety/Violence" for t in topics_after)
        assert any(t.path == "Safety" for t in topics_after)

        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        for t in tests:
            assert t.topic in ("", "Safety")
            assert not t.topic.startswith("Safety/Violence")

    def test_removes_intermediate_topic_and_subtopic_markers(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Removing an intermediate topic should remove it and all subtopic markers."""
        topics_before = get_tree_topics(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert any(t.path == "Europe/Germany" for t in topics_before)
        assert any(t.path == "Europe/Germany/Berlin" for t in topics_before)

        result = remove_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe/Germany",
        )

        assert result is True

        topics_after = get_tree_topics(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert not any(t.path == "Europe/Germany" for t in topics_after)
        assert not any(t.path == "Europe/Germany/Berlin" for t in topics_after)
        assert any(t.path == "Europe" for t in topics_after)

        tests = get_tree_tests(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        for t in tests:
            assert t.topic in ("", "Europe")
            assert not t.topic.startswith("Europe/Germany")

    def test_topic_markers_do_not_remain_in_database(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Topic marker tests must be soft-deleted; none must remain active in DB."""
        nodes_before = get_tree_nodes(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        marker_ids_before = {
            n.id for n in nodes_before if n.topic == "Europe/Germany" and n.label == "topic_marker"
        }
        marker_ids_before.update(
            n.id
            for n in nodes_before
            if n.topic == "Europe/Germany/Berlin" and n.label == "topic_marker"
        )
        assert len(marker_ids_before) == 2, (
            "Fixture should have 2 topic markers under Europe/Germany"
        )

        remove_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe/Germany",
        )

        nodes_after = get_tree_nodes(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        for n in nodes_after:
            assert (n.topic, n.label) != ("Europe/Germany", "topic_marker")
            assert (n.topic, n.label) != ("Europe/Germany/Berlin", "topic_marker")

        with without_soft_delete_filter():
            for test_id in marker_ids_before:
                db_test = test_db.query(models.Test).filter(models.Test.id == test_id).first()
                assert db_test is not None
                assert db_test.deleted_at is not None, (
                    f"Topic marker test {test_id} must be soft-deleted and not remain in DB"
                )

    def test_topic_markers_removed_from_tree_after_remove(
        self, test_db, adaptive_test_set, test_org_id, authenticated_user_id
    ):
        """After removing a topic, no topic marker for that path may appear in the tree."""
        nodes_before = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        violence_marker_ids = [
            n.id for n in nodes_before if n.topic == "Safety/Violence" and n.label == "topic_marker"
        ]
        assert len(violence_marker_ids) == 1

        remove_topic_node(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Safety/Violence",
        )

        nodes_after = get_tree_nodes(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        violence_markers_after = [
            n for n in nodes_after if n.topic == "Safety/Violence" and n.label == "topic_marker"
        ]
        assert len(violence_markers_after) == 0, (
            "Topic markers for removed topic must not remain in tree"
        )

        with without_soft_delete_filter():
            for test_id in violence_marker_ids:
                db_test = test_db.query(models.Test).filter(models.Test.id == test_id).first()
                assert db_test is not None
                assert db_test.deleted_at is not None, "Topic marker must be soft-deleted"


# ============================================================================
# Tests for update_topic_node
# ============================================================================


@pytest.mark.integration
@pytest.mark.service
class TestUpdateTopicNode:
    """Test update_topic_node - renames topics in a test set."""

    def test_rename_leaf_topic(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Renaming a leaf topic should update its path."""
        result = update_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe/Germany/Berlin",
            new_name="Munich",
        )

        assert result is not None
        assert result.path == "Europe/Germany/Munich"

        # Verify the old topic is gone and new one exists in the tree
        topics = get_tree_topics(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}
        assert "Europe/Germany/Berlin" not in topic_paths
        assert "Europe/Germany/Munich" in topic_paths

    def test_rename_middle_topic_cascades_to_children(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Renaming a middle topic should cascade to all children."""
        result = update_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe/Germany",
            new_name="Deutschland",
        )

        assert result is not None
        assert result.path == "Europe/Deutschland"

        topics = get_tree_topics(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}

        # Old paths should be gone
        assert "Europe/Germany" not in topic_paths
        assert "Europe/Germany/Berlin" not in topic_paths

        # New paths should exist
        assert "Europe/Deutschland" in topic_paths
        assert "Europe/Deutschland/Berlin" in topic_paths

        # Europe (parent) should be unchanged
        assert "Europe" in topic_paths

    def test_rename_root_level_topic(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Renaming a root-level topic should cascade to all descendants."""
        result = update_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe",
            new_name="EU",
        )

        assert result is not None
        assert result.path == "EU"

        topics = get_tree_topics(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}

        assert "Europe" not in topic_paths
        assert "Europe/Germany" not in topic_paths
        assert "Europe/Germany/Berlin" not in topic_paths

        assert "EU" in topic_paths
        assert "EU/Germany" in topic_paths
        assert "EU/Germany/Berlin" in topic_paths

    def test_rename_updates_tests_topic(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Tests under the renamed topic should reference the new path."""
        update_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe/Germany",
            new_name="Deutschland",
        )

        tests = get_tree_tests(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # The test that was under Europe/Germany should now be under
        # Europe/Deutschland
        germany_test = next(t for t in tests if t.input == "Question about Germany")
        assert germany_test.topic == "Europe/Deutschland"

        # The test that was under Europe/Germany/Berlin should now be
        # under Europe/Deutschland/Berlin
        berlin_test = next(t for t in tests if t.input == "Question about Berlin")
        assert berlin_test.topic == "Europe/Deutschland/Berlin"

        # The Europe test should remain unchanged
        europe_test = next(t for t in tests if t.input == "Question about Europe")
        assert europe_test.topic == "Europe"

    def test_rename_nonexistent_topic_returns_none(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Should return None when the topic does not exist."""
        result = update_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="NonExistent/Topic",
            new_name="NewName",
        )

        assert result is None

    def test_rename_with_slash_raises_value_error(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Should raise ValueError if new_name contains a slash."""
        with pytest.raises(ValueError, match="must not contain"):
            update_topic_node(
                db=test_db,
                test_set_id=deep_topic_test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                topic_path="Europe/Germany",
                new_name="Deutsch/land",
            )

    def test_rename_to_same_name_is_noop(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Renaming to the same name should return the topic unchanged."""
        result = update_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe/Germany",
            new_name="Germany",
        )

        assert result is not None
        assert result.path == "Europe/Germany"

        # Verify tree is unchanged
        topics = get_tree_topics(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        topic_paths = {t.path for t in topics}
        assert "Europe/Germany" in topic_paths
        assert "Europe/Germany/Berlin" in topic_paths

    def test_rename_preserves_node_count(
        self, test_db, deep_topic_test_set, test_org_id, authenticated_user_id
    ):
        """Renaming should not change the total number of nodes."""
        nodes_before = get_tree_nodes(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        update_topic_node(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_path="Europe/Germany",
            new_name="Deutschland",
        )

        nodes_after = get_tree_nodes(
            db=test_db,
            test_set_id=deep_topic_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert len(nodes_after) == len(nodes_before)

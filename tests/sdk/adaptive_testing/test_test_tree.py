"""Unit tests for TestTree to_test_set and from_test_set methods."""

import pytest

from rhesis.sdk.adaptive_testing import TestTree
from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode
from rhesis.sdk.entities import Prompt, Test, TestSet


class TestTestTreeToTestSet:
    """Tests for TestTree.to_test_set() method."""

    @pytest.fixture
    def simple_tree(self):
        """Create a simple TestTree with a few tests."""
        nodes = [
            TestTreeNode(
                id="1",
                topic="Safety",
                input="Is this safe?",
                output="Yes it is",
                label="pass",
                labeler="user",
            ),
            TestTreeNode(
                id="2",
                topic="Safety",
                input="What about this?",
                output="No it isn't",
                label="fail",
                labeler="user",
            ),
            TestTreeNode(
                id="3",
                topic="Safety/Violence",
                input="Is violence ok?",
                output="Never",
                label="fail",
                labeler="user",
            ),
        ]
        return TestTree(TestTreeData(nodes=nodes))

    @pytest.fixture
    def tree_with_topic_marker(self):
        """Create a TestTree with a topic marker."""
        nodes = [
            TestTreeNode(
                id="marker-1",
                topic="Safety",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
            TestTreeNode(
                id="1",
                topic="Safety",
                input="Is this safe?",
                output="Yes",
                label="pass",
                labeler="user",
            ),
        ]
        return TestTree(TestTreeData(nodes=nodes))

    @pytest.fixture
    def tree_with_suggestions(self):
        """Create a TestTree with suggestions."""
        nodes = [
            TestTreeNode(
                id="1",
                topic="/Safety",
                input="Is this safe?",
                output="Yes",
                label="pass",
                labeler="user",
            ),
            TestTreeNode(
                id="2",
                topic="/Safety/__suggestions__",
                input="Suggested test",
                output="[no output]",
                label="",
                labeler="imputed",
            ),
        ]
        return TestTree(TestTreeData(nodes=nodes))

    @pytest.fixture
    def empty_tree(self):
        """Create an empty TestTree."""
        return TestTree(TestTreeData(nodes=[]))

    def test_to_test_set_returns_test_set(self, simple_tree):
        """to_test_set should return a TestSet instance."""
        result = simple_tree.to_test_set()
        assert isinstance(result, TestSet)

    def test_to_test_set_contains_tests(self, simple_tree):
        """to_test_set should contain Test objects."""
        result = simple_tree.to_test_set()
        assert result.tests is not None
        assert len(result.tests) > 0
        assert all(isinstance(t, Test) for t in result.tests)

    def test_to_test_set_preserves_topic_path(self, simple_tree):
        """to_test_set should preserve the full topic path."""
        result = simple_tree.to_test_set()

        topics = [t.topic for t in result.tests]
        assert "Safety" in topics
        assert "Safety/Violence" in topics

    def test_to_test_set_stores_input_as_prompt(self, simple_tree):
        """to_test_set should store input in Prompt.content."""
        result = simple_tree.to_test_set()

        for test in result.tests:
            assert test.prompt is not None
            assert test.prompt.content is not None
            assert len(test.prompt.content) > 0

    def test_to_test_set_stores_output_in_metadata(self, simple_tree):
        """to_test_set should store output in metadata for round-trip."""
        result = simple_tree.to_test_set()

        for test in result.tests:
            assert "output" in test.metadata
            assert test.metadata["output"] is not None

    def test_to_test_set_stores_label_in_metadata(self, simple_tree):
        """to_test_set should store label in metadata for round-trip."""
        result = simple_tree.to_test_set()

        for test in result.tests:
            assert "label" in test.metadata

    def test_to_test_set_excludes_suggestions_by_default(self, tree_with_suggestions):
        """to_test_set should exclude __suggestions__ by default."""
        result = tree_with_suggestions.to_test_set(include_suggestions=False)

        for test in result.tests:
            assert "/__suggestions__" not in test.topic

    def test_to_test_set_includes_suggestions_when_requested(self, tree_with_suggestions):
        """to_test_set should include __suggestions__ when requested."""
        result = tree_with_suggestions.to_test_set(include_suggestions=True)

        topics = [t.topic for t in result.tests]
        suggestion_topics = [t for t in topics if "/__suggestions__" in t]
        assert len(suggestion_topics) > 0

    def test_to_test_set_empty_tree(self, empty_tree):
        """to_test_set on empty tree should return TestSet with empty tests."""
        result = empty_tree.to_test_set()
        assert isinstance(result, TestSet)
        assert result.tests == []

    def test_to_test_set_uses_tree_name(self, simple_tree):
        """to_test_set should use the tree's name for the TestSet."""
        result = simple_tree.to_test_set()
        assert result.name == simple_tree.name


class TestTestTreeFromTestSet:
    """Tests for TestTree.from_test_set() class method."""

    @pytest.fixture
    def simple_test_set(self):
        """Create a simple TestSet with tests."""
        tests = [
            Test(
                id="1",
                topic="/Safety",
                prompt=Prompt(content="Is this safe?"),
                behavior="Test",
                category="Test",
            ),
            Test(
                id="2",
                topic="/Safety/Violence",
                prompt=Prompt(content="Is violence ok?"),
                behavior="Test",
                category="Test",
            ),
        ]
        return TestSet(name="Test Set", tests=tests)

    @pytest.fixture
    def empty_test_set(self):
        """Create an empty TestSet."""
        return TestSet(name="Empty", tests=[])

    @pytest.fixture
    def test_set_with_multi_turn(self):
        """Create a TestSet with multi-turn tests (no prompt)."""
        tests = [
            Test(
                topic="/Safety",
                id="1",
                prompt=Prompt(content="Single turn test"),
                behavior="Test",
                category="Test",
            ),
            Test(
                topic="/MultiTurn",
                prompt=None,  # Multi-turn tests don't have prompts
                behavior="Test",
                category="Test",
                id="2",
            ),
        ]
        return TestSet(name="Mixed", tests=tests)

    def test_from_test_set_returns_test_tree_data(self, simple_test_set):
        """from_test_set should return a TestTreeData instance."""
        result = TestTree.from_test_set(simple_test_set)
        assert isinstance(result, TestTreeData)

    def test_from_test_set_preserves_topics(self, simple_test_set):
        """from_test_set should preserve topic paths."""
        result = TestTree.from_test_set(simple_test_set)

        topics = [node.topic for node in result]
        # Topics are preserved as-is (no URL encoding)
        assert "/Safety" in topics or any("/Safety" in t for t in topics)

    def test_from_test_set_preserves_input(self, simple_test_set):
        """from_test_set should preserve prompt content as input."""
        result = TestTree.from_test_set(simple_test_set)

        inputs = [node.input for node in result]
        assert "Is this safe?" in inputs
        assert "Is violence ok?" in inputs

    def test_from_test_set_sets_default_output(self, simple_test_set):
        """from_test_set should set output to '[no output]' when not in metadata."""
        result = TestTree.from_test_set(simple_test_set)

        outputs = [node.output for node in result]
        assert all(o == "[no output]" for o in outputs)

    def test_from_test_set_empty(self, empty_test_set):
        """from_test_set on empty TestSet should return empty TestTreeData."""
        result = TestTree.from_test_set(empty_test_set)
        assert isinstance(result, TestTreeData)
        assert len(result) == 0

    def test_from_test_set_skips_multi_turn(self, test_set_with_multi_turn):
        """from_test_set should skip multi-turn tests (no prompt)."""
        result = TestTree.from_test_set(test_set_with_multi_turn)

        # Should only have the single-turn test
        assert len(result) == 1
        assert result[0].input == "Single turn test"


class TestTestTreeRoundTrip:
    """Tests for round-trip conversion TestTree -> TestSet -> TestTree."""

    @pytest.fixture
    def original_tree(self):
        """Create a TestTree for round-trip testing."""
        nodes = [
            TestTreeNode(
                id="1",
                topic="/Category/Topic1",
                input="Test input 1",
                output="Output 1",
                label="pass",
                labeler="user",
                model_score=0.9,
            ),
            TestTreeNode(
                id="2",
                topic="/Category/Topic2",
                input="Test input 2",
                output="Output 2",
                label="fail",
                labeler="scored",
                model_score=0.3,
            ),
            TestTreeNode(
                id="3",
                topic="/Other",
                input="Test input 3",
                output="[no output]",
                label="",
                labeler="imputed",
                model_score=0.0,
            ),
        ]
        return TestTree(TestTreeData(nodes=nodes))

    def test_round_trip_preserves_test_count(self, original_tree):
        """Round-trip should preserve the number of actual tests."""
        # Get count of actual tests (not topic markers)
        original_tests = [node for node in original_tree._tests if node.label != "topic_marker"]
        original_count = len(original_tests)

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_data = TestTree.from_test_set(test_set)

        # Count tests in restored data
        assert len(restored_data) == original_count

    def test_round_trip_preserves_inputs(self, original_tree):
        """Round-trip should preserve all input values."""
        # Get original inputs (excluding topic markers)
        original_inputs = set(
            node.input for node in original_tree._tests if node.label != "topic_marker"
        )

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_data = TestTree.from_test_set(test_set)

        # Get restored inputs
        restored_inputs = set(node.input for node in restored_data)

        assert original_inputs == restored_inputs

    def test_round_trip_preserves_outputs(self, original_tree):
        """Round-trip should preserve all output values."""
        # Get original outputs (excluding topic markers)
        original_outputs = set(
            node.output for node in original_tree._tests if node.label != "topic_marker"
        )

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_data = TestTree.from_test_set(test_set)

        # Get restored outputs
        restored_outputs = set(node.output for node in restored_data)

        assert original_outputs == restored_outputs

    def test_round_trip_preserves_labels(self, original_tree):
        """Round-trip should preserve all label values."""
        # Get original labels (excluding topic markers)
        original_labels = [
            node.label for node in original_tree._tests if node.label != "topic_marker"
        ]

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_data = TestTree.from_test_set(test_set)

        # Get restored labels
        restored_labels = [node.label for node in restored_data]

        assert sorted(original_labels) == sorted(restored_labels)

    def test_round_trip_preserves_model_scores(self, original_tree):
        """Round-trip should preserve model_score values."""
        # Get original scores (excluding topic markers)
        original_scores = [
            node.model_score for node in original_tree._tests if node.label != "topic_marker"
        ]

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_data = TestTree.from_test_set(test_set)

        # Get restored scores
        restored_scores = [node.model_score for node in restored_data]

        assert sorted(original_scores) == sorted(restored_scores)

    def test_round_trip_test_set_has_correct_count(self, original_tree):
        """TestSet should have same number of tests as non-marker rows."""
        original_tests = [node for node in original_tree._tests if node.label != "topic_marker"]

        test_set = original_tree.to_test_set()

        assert len(test_set.tests) == len(original_tests)


class TestTestTreeDataValidate:
    """Tests for TestTreeData.validate() method."""

    @pytest.fixture
    def valid_data(self):
        """Create a valid TestTreeData with all topic markers present."""
        nodes = [
            # Topic markers
            TestTreeNode(
                id="marker-1",
                topic="/Safety",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
            TestTreeNode(
                id="marker-2",
                topic="/Safety/Violence",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
            # Actual tests
            TestTreeNode(
                id="1",
                topic="/Safety",
                input="Is this safe?",
                output="Yes",
                label="pass",
                labeler="user",
            ),
            TestTreeNode(
                id="2",
                topic="/Safety/Violence",
                input="Is violence ok?",
                output="No",
                label="fail",
                labeler="user",
            ),
        ]
        return TestTreeData(nodes=nodes)

    @pytest.fixture
    def invalid_data_missing_marker(self):
        """Create a TestTreeData missing a topic marker."""
        nodes = [
            # Only marker for /Safety, but tests exist in /Safety/Violence
            TestTreeNode(
                id="marker-1",
                topic="/Safety",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
            TestTreeNode(
                id="1",
                topic="/Safety",
                input="Is this safe?",
                output="Yes",
                label="pass",
                labeler="user",
            ),
            # This test has no corresponding topic marker
            TestTreeNode(
                id="2",
                topic="/Safety/Violence",
                input="Is violence ok?",
                output="No",
                label="fail",
                labeler="user",
            ),
        ]
        return TestTreeData(nodes=nodes)

    @pytest.fixture
    def invalid_data_missing_parent_marker(self):
        """Create a TestTreeData missing a parent topic marker."""
        nodes = [
            # Marker for /Safety/Violence but not for /Safety
            TestTreeNode(
                id="marker-1",
                topic="/Safety/Violence",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
            TestTreeNode(
                id="1",
                topic="/Safety/Violence",
                input="Is violence ok?",
                output="No",
                label="fail",
                labeler="user",
            ),
        ]
        return TestTreeData(nodes=nodes)

    @pytest.fixture
    def empty_data(self):
        """Create an empty TestTreeData."""
        return TestTreeData(nodes=[])

    @pytest.fixture
    def data_with_only_markers(self):
        """Create a TestTreeData with only topic markers (no actual tests)."""
        nodes = [
            TestTreeNode(
                id="marker-1",
                topic="/Safety",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
        ]
        return TestTreeData(nodes=nodes)

    def test_validate_returns_dict(self, valid_data):
        """validate should return a dictionary."""
        result = valid_data.validate()
        assert isinstance(result, dict)

    def test_validate_has_required_keys(self, valid_data):
        """validate should return dict with all required keys."""
        result = valid_data.validate()
        assert "valid" in result
        assert "missing_markers" in result
        assert "topics_with_tests" in result
        assert "topics_with_markers" in result

    def test_validate_valid_data_is_valid(self, valid_data):
        """validate on valid data should return valid=True."""
        result = valid_data.validate()
        assert result["valid"] is True
        assert result["missing_markers"] == []

    def test_validate_valid_data_has_correct_topics(self, valid_data):
        """validate should correctly identify topics with tests and markers."""
        result = valid_data.validate()
        assert "/Safety" in result["topics_with_tests"]
        assert "/Safety/Violence" in result["topics_with_tests"]
        assert "/Safety" in result["topics_with_markers"]
        assert "/Safety/Violence" in result["topics_with_markers"]

    def test_validate_invalid_data_missing_marker(self, invalid_data_missing_marker):
        """validate should detect missing topic marker."""
        result = invalid_data_missing_marker.validate()
        assert result["valid"] is False
        assert "/Safety/Violence" in result["missing_markers"]

    def test_validate_invalid_data_missing_parent_marker(self, invalid_data_missing_parent_marker):
        """validate should detect missing parent topic marker."""
        result = invalid_data_missing_parent_marker.validate()
        assert result["valid"] is False
        assert "/Safety" in result["missing_markers"]

    def test_validate_empty_data(self, empty_data):
        """validate on empty data should return valid=True."""
        result = empty_data.validate()
        assert result["valid"] is True
        assert result["missing_markers"] == []
        assert result["topics_with_tests"] == []
        assert result["topics_with_markers"] == []

    def test_validate_data_with_only_markers(self, data_with_only_markers):
        """validate on data with only markers should return valid=True."""
        result = data_with_only_markers.validate()
        assert result["valid"] is True
        assert result["missing_markers"] == []
        # No actual tests, so topics_with_tests should be empty
        assert result["topics_with_tests"] == []
        assert "/Safety" in result["topics_with_markers"]

    def test_validate_nested_topics_require_all_parents(self):
        """validate should require markers for all parent topics."""
        nodes = [
            # Only marker for deepest level
            TestTreeNode(
                id="marker-1",
                topic="/A/B/C",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
            TestTreeNode(
                id="1",
                topic="/A/B/C",
                input="Test",
                output="Output",
                label="pass",
                labeler="user",
            ),
        ]
        data = TestTreeData(nodes=nodes)
        result = data.validate()

        assert result["valid"] is False
        # Should require markers for /A and /A/B
        assert "/A" in result["missing_markers"]
        assert "/A/B" in result["missing_markers"]

    def test_validate_multiple_tests_same_topic(self):
        """validate should work with multiple tests in the same topic."""
        nodes = [
            TestTreeNode(
                id="marker-1",
                topic="/Safety",
                input="",
                output="",
                label="topic_marker",
                labeler="",
            ),
            TestTreeNode(
                id="1",
                topic="/Safety",
                input="Test 1",
                output="Output 1",
                label="pass",
                labeler="user",
            ),
            TestTreeNode(
                id="2",
                topic="/Safety",
                input="Test 2",
                output="Output 2",
                label="fail",
                labeler="user",
            ),
            TestTreeNode(
                id="3",
                topic="/Safety",
                input="Test 3",
                output="Output 3",
                label="pass",
                labeler="user",
            ),
        ]
        data = TestTreeData(nodes=nodes)
        result = data.validate()

        assert result["valid"] is True
        assert "/Safety" in result["topics_with_tests"]

    def test_validate_returns_sorted_lists(self, valid_data):
        """validate should return sorted lists."""
        result = valid_data.validate()
        assert result["missing_markers"] == sorted(result["missing_markers"])
        assert result["topics_with_tests"] == sorted(result["topics_with_tests"])
        assert result["topics_with_markers"] == sorted(result["topics_with_markers"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

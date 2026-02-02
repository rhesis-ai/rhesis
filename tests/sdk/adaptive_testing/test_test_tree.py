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
                topic="/Safety",
                input="Is this safe?",
                output="Yes it is",
                label="pass",
                labeler="user",
            ),
            TestTreeNode(
                id="2",
                topic="/Safety",
                input="What about this?",
                output="No it isn't",
                label="fail",
                labeler="user",
            ),
            TestTreeNode(
                id="3",
                topic="/Safety/Violence",
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

    def test_to_test_set_excludes_topic_markers(self, tree_with_topic_marker):
        """to_test_set should not include topic_marker rows."""
        result = tree_with_topic_marker.to_test_set()

        # Count non-topic-marker rows in original tree
        actual_tests = [
            node for node in tree_with_topic_marker._tests if node.label != "topic_marker"
        ]
        assert len(result.tests) == len(actual_tests)

    def test_to_test_set_preserves_topic_path(self, simple_tree):
        """to_test_set should preserve the full topic path."""
        result = simple_tree.to_test_set()

        topics = [t.topic for t in result.tests]
        assert "/Safety" in topics
        assert "/Safety/Violence" in topics

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
                topic="/Safety",
                prompt=Prompt(content="Is this safe?"),
                metadata={"tree_id": "abc123"},
                behavior="Test",
                category="Test",
            ),
            Test(
                topic="/Safety/Violence",
                prompt=Prompt(content="Is violence ok?"),
                metadata={"tree_id": "def456"},
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
                prompt=Prompt(content="Single turn test"),
                behavior="Test",
                category="Test",
            ),
            Test(
                topic="/MultiTurn",
                prompt=None,  # Multi-turn tests don't have prompts
                behavior="Test",
                category="Test",
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
        # Topics should be URI-encoded (spaces become %20)
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

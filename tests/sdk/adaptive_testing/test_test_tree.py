"""Unit tests for TestTree to_test_set and from_test_set methods."""

import pandas as pd
import pytest

from rhesis.sdk.adaptive_testing import TestTree
from rhesis.sdk.entities import Prompt, Test, TestSet


class TestTestTreeToTestSet:
    """Tests for TestTree.to_test_set() method."""

    @pytest.fixture
    def simple_tree(self):
        """Create a simple TestTree with a few tests."""
        data = {
            "topic": ["/Safety", "/Safety", "/Safety/Violence"],
            "input": ["Is this safe?", "What about this?", "Is violence ok?"],
            "output": ["Yes it is", "No it isn't", "Never"],
            "label": ["pass", "fail", "fail"],
            "labeler": ["user", "user", "user"],
        }
        df = pd.DataFrame(data)
        return TestTree(df, ensure_topic_markers=True)

    @pytest.fixture
    def tree_with_suggestions(self):
        """Create a TestTree with suggestions."""
        data = {
            "topic": ["/Safety", "/Safety/__suggestions__"],
            "input": ["Is this safe?", "Suggested test"],
            "output": ["Yes", "[no output]"],
            "label": ["pass", ""],
            "labeler": ["user", "imputed"],
        }
        df = pd.DataFrame(data)
        return TestTree(df, ensure_topic_markers=True)

    @pytest.fixture
    def empty_tree(self):
        """Create an empty TestTree."""
        return TestTree()

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

    def test_to_test_set_excludes_topic_markers(self, simple_tree):
        """to_test_set should not include topic_marker rows."""
        result = simple_tree.to_test_set()

        # Count non-topic-marker rows in original tree
        actual_tests = simple_tree._tests[simple_tree._tests["label"] != "topic_marker"]
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

    def test_to_test_set_does_not_store_output(self, simple_tree):
        """to_test_set should NOT store output (it's execution data)."""
        result = simple_tree.to_test_set()

        for test in result.tests:
            # Output should not be in expected_response
            assert test.prompt.expected_response is None
            # Output should not be in metadata
            assert "output" not in (test.metadata or {})

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
            ),
            Test(
                topic="/Safety/Violence",
                prompt=Prompt(content="Is violence ok?"),
                metadata={"tree_id": "def456"},
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
            ),
            Test(
                topic="/MultiTurn",
                prompt=None,  # Multi-turn tests don't have prompts
                test_configuration={"goal": "Test the system"},
            ),
        ]
        return TestSet(name="Mixed", tests=tests)

    def test_from_test_set_returns_test_tree(self, simple_test_set):
        """from_test_set should return a TestTree instance."""
        result = TestTree.from_test_set(simple_test_set)
        assert isinstance(result, TestTree)

    def test_from_test_set_preserves_topics(self, simple_test_set):
        """from_test_set should preserve topic paths."""
        result = TestTree.from_test_set(simple_test_set)

        topics = list(result._tests["topic"])
        # Topics should be URI-encoded (spaces become %20)
        assert "/Safety" in topics or "/Safety" in [t.replace("%20", " ") for t in topics]

    def test_from_test_set_preserves_input(self, simple_test_set):
        """from_test_set should preserve prompt content as input."""
        result = TestTree.from_test_set(simple_test_set)

        inputs = list(result._tests["input"])
        assert "Is this safe?" in inputs
        assert "Is violence ok?" in inputs

    def test_from_test_set_sets_no_output(self, simple_test_set):
        """from_test_set should set output to '[no output]'."""
        result = TestTree.from_test_set(simple_test_set)

        outputs = list(result._tests["output"])
        assert all(o == "[no output]" for o in outputs if o)

    def test_from_test_set_tracks_test_set_id(self, simple_test_set):
        """from_test_set should track the source test_set_id."""
        simple_test_set.id = "test-set-uuid"
        result = TestTree.from_test_set(simple_test_set)

        assert hasattr(result, "_test_set_id")
        assert result._test_set_id == "test-set-uuid"

    def test_from_test_set_empty(self, empty_test_set):
        """from_test_set on empty TestSet should return empty TestTree."""
        result = TestTree.from_test_set(empty_test_set)
        assert isinstance(result, TestTree)
        assert len(result._tests) == 0

    def test_from_test_set_skips_multi_turn(self, test_set_with_multi_turn):
        """from_test_set should skip multi-turn tests (no prompt)."""
        result = TestTree.from_test_set(test_set_with_multi_turn)

        # Should only have the single-turn test
        assert len(result._tests[result._tests["label"] != "topic_marker"]) == 1
        inputs = list(result._tests["input"])
        assert "Single turn test" in inputs

    def test_from_test_set_creates_topic_markers(self, simple_test_set):
        """from_test_set should create topic markers for hierarchy."""
        result = TestTree.from_test_set(simple_test_set)

        topic_markers = result._tests[result._tests["label"] == "topic_marker"]
        assert len(topic_markers) > 0


class TestTestTreeRoundTrip:
    """Tests for round-trip conversion TestTree -> TestSet -> TestTree."""

    @pytest.fixture
    def original_tree(self):
        """Create a TestTree for round-trip testing."""
        data = {
            "topic": ["/Category/Topic1", "/Category/Topic2", "/Other"],
            "input": ["Test input 1", "Test input 2", "Test input 3"],
            "output": ["Output 1", "Output 2", "[no output]"],
            "label": ["pass", "fail", ""],
            "labeler": ["user", "scored", "imputed"],
        }
        df = pd.DataFrame(data)
        return TestTree(df, ensure_topic_markers=True)

    def test_round_trip_preserves_test_count(self, original_tree):
        """Round-trip should preserve the number of actual tests."""
        # Get count of actual tests (not topic markers)
        original_tests = original_tree._tests[original_tree._tests["label"] != "topic_marker"]
        original_count = len(original_tests)

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_tree = TestTree.from_test_set(test_set)

        # Count tests in restored tree (excluding topic markers)
        restored_tests = restored_tree._tests[restored_tree._tests["label"] != "topic_marker"]
        assert len(restored_tests) == original_count

    def test_round_trip_preserves_inputs(self, original_tree):
        """Round-trip should preserve all input values."""
        # Get original inputs (excluding topic markers)
        original_inputs = set(
            original_tree._tests[original_tree._tests["label"] != "topic_marker"]["input"]
        )

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_tree = TestTree.from_test_set(test_set)

        # Get restored inputs
        restored_inputs = set(
            restored_tree._tests[restored_tree._tests["label"] != "topic_marker"]["input"]
        )

        assert original_inputs == restored_inputs

    def test_round_trip_preserves_topics(self, original_tree):
        """Round-trip should preserve topic paths."""
        # Get original topics
        original_topics = set(
            original_tree._tests[original_tree._tests["label"] != "topic_marker"]["topic"]
        )

        # Convert to TestSet and back
        test_set = original_tree.to_test_set()
        restored_tree = TestTree.from_test_set(test_set)

        # Get restored topics
        restored_topics = set(
            restored_tree._tests[restored_tree._tests["label"] != "topic_marker"]["topic"]
        )

        assert original_topics == restored_topics

    def test_round_trip_test_set_has_correct_count(self, original_tree):
        """TestSet should have same number of tests as non-marker rows."""
        original_tests = original_tree._tests[original_tree._tests["label"] != "topic_marker"]

        test_set = original_tree.to_test_set()

        assert len(test_set.tests) == len(original_tests)

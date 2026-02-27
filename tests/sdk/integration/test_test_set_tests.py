"""Integration tests for TestSet test association methods (add_tests / remove_tests).

These tests require a running backend (via docker-compose) and
exercise the full HTTP path: SDK -> backend API -> database.
"""

import pytest

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _create_test_set(
    name: str = "Association Test Set", num_tests: int = 1
) -> TestSet:
    """Create a test set with the given number of tests via the bulk endpoint."""
    tests = [
        {
            "category": "Safety",
            "topic": "Content",
            "behavior": f"Behavior{i}",
            "prompt": {"content": f"Test prompt {i}"},
        }
        for i in range(num_tests)
    ]
    ts = TestSet(
        name=name,
        description="Integration test set for test association",
        short_description="Test",
        test_set_type=TestType.SINGLE_TURN,
        tests=tests,
    )
    ts.push()
    assert ts.id is not None, "Test set creation failed"
    ts.fetch_tests()
    return ts


def _get_test_ids(ts: TestSet) -> list[str]:
    """Return the list of test IDs from a test set."""
    assert ts.tests, "Test set has no tests"
    return [t.id for t in ts.tests]


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestAddTests:
    """Tests for TestSet.add_tests()."""

    def test_add_tests_by_instance(self, db_cleanup):
        """Add tests using Test instances."""
        source = _create_test_set("Source", num_tests=2)
        target = _create_test_set("Target")

        result = target.add_tests(source.tests)

        assert result is not None
        assert result["success"] is True

    def test_add_tests_by_uuid(self, db_cleanup):
        """Add tests using UUID strings."""
        source = _create_test_set("Source", num_tests=1)
        target = _create_test_set("Target")
        test_ids = _get_test_ids(source)

        result = target.add_tests(test_ids)

        assert result is not None
        assert result["success"] is True

    def test_add_tests_by_dict(self, db_cleanup):
        """Add tests using dicts with 'id' key."""
        source = _create_test_set("Source", num_tests=1)
        target = _create_test_set("Target")
        test_dicts = [{"id": t.id} for t in source.tests]

        result = target.add_tests(test_dicts)

        assert result is not None
        assert result["success"] is True

    def test_add_tests_reflected_in_fetch(self, db_cleanup):
        """After add_tests, fetch_tests returns the new tests."""
        source = _create_test_set("Source", num_tests=2)
        target = _create_test_set("Target")
        initial_count = len(target.fetch_tests())

        target.add_tests(source.tests)

        updated_tests = target.fetch_tests()
        assert len(updated_tests) == initial_count + 2

    def test_add_tests_mixed_references(self, db_cleanup):
        """Add tests using a mix of instances, dicts, and UUIDs."""
        source = _create_test_set("Source", num_tests=3)
        target = _create_test_set("Target")
        tests = source.tests

        result = target.add_tests([
            tests[0],
            {"id": tests[1].id},
            str(tests[2].id),
        ])

        assert result is not None
        assert result["success"] is True

    def test_add_tests_requires_id(self, db_cleanup):
        """add_tests raises if test set has no ID."""
        source = _create_test_set("Source")

        ts = TestSet(name="No ID")
        with pytest.raises(ValueError, match="Test set ID must be set"):
            ts.add_tests(source.tests)


class TestRemoveTests:
    """Tests for TestSet.remove_tests()."""

    def test_remove_tests_by_instance(self, db_cleanup):
        """Remove tests using Test instances."""
        source = _create_test_set("Source")
        target = _create_test_set("Target")
        target.add_tests(source.tests)

        result = target.remove_tests(source.tests)

        assert result is not None
        assert result["success"] is True
        assert result["removed_associations"] == 1

    def test_remove_tests_by_uuid(self, db_cleanup):
        """Remove tests using UUID strings."""
        source = _create_test_set("Source")
        target = _create_test_set("Target")
        target.add_tests(source.tests)

        result = target.remove_tests(_get_test_ids(source))

        assert result is not None
        assert result["success"] is True
        assert result["removed_associations"] == 1

    def test_remove_tests_reflected_in_fetch(self, db_cleanup):
        """After remove_tests, fetch_tests no longer returns them."""
        source = _create_test_set("Source")
        target = _create_test_set("Target")
        initial_count = len(target.fetch_tests())

        target.add_tests(source.tests)
        assert len(target.fetch_tests()) == initial_count + 1

        target.remove_tests(source.tests)
        assert len(target.fetch_tests()) == initial_count

    def test_remove_tests_requires_id(self, db_cleanup):
        """remove_tests raises if test set has no ID."""
        ts = TestSet(name="No ID")

        with pytest.raises(ValueError, match="Test set ID must be set"):
            ts.remove_tests(["some-uuid"])


class TestAddRemoveRoundTrip:
    """Tests for add + remove lifecycle."""

    def test_add_then_remove_all(self, db_cleanup):
        """Adding and removing tests leaves the set at original count."""
        source = _create_test_set("Source", num_tests=2)
        target = _create_test_set("Target")
        initial_count = len(target.fetch_tests())

        target.add_tests(source.tests)
        assert len(target.fetch_tests()) == initial_count + 2

        target.remove_tests(source.tests)
        assert len(target.fetch_tests()) == initial_count

    def test_add_multiple_then_remove_one(self, db_cleanup):
        """Removing one test leaves others intact."""
        source = _create_test_set("Source", num_tests=2)
        target = _create_test_set("Target")
        initial_count = len(target.fetch_tests())

        target.add_tests(source.tests)
        assert len(target.fetch_tests()) == initial_count + 2

        target.remove_tests([source.tests[0]])
        remaining = target.fetch_tests()
        assert len(remaining) == initial_count + 1
        remaining_ids = [t.id for t in remaining]
        assert source.tests[1].id in remaining_ids

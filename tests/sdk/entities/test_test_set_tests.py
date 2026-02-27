import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.entities.test import Test
from rhesis.sdk.entities.test_set import TestSet

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


# --- Fixtures ---


@pytest.fixture
def test_set():
    return TestSet(
        id="ts-111",
        name="Safety Tests",
        description="Safety test set",
        short_description="Safety",
    )


@pytest.fixture
def test_set_no_id():
    return TestSet(
        name="Safety Tests",
        description="Safety test set",
        short_description="Safety",
    )


# ================================================================
# Tests for _resolve_test_id()
# ================================================================


class TestResolveTestId:
    """Tests for TestSet._resolve_test_id()."""

    def test_resolve_test_instance(self, test_set):
        """Test instance with id returns its id."""
        t = Test(id="t-123", category="Safety", behavior="Compliance")
        assert test_set._resolve_test_id(t) == "t-123"

    def test_resolve_dict_with_id(self, test_set):
        """Dict with 'id' key returns the id."""
        assert test_set._resolve_test_id({"id": "t-456"}) == "t-456"

    def test_resolve_dict_missing_id_raises(self, test_set):
        """Dict without 'id' key raises ValueError."""
        with pytest.raises(ValueError, match="must contain an 'id' key"):
            test_set._resolve_test_id({"name": "no id here"})

    def test_resolve_uuid_string(self, test_set):
        """Valid UUID string is returned as-is."""
        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert test_set._resolve_test_id(uuid) == uuid

    def test_resolve_invalid_string_raises(self, test_set):
        """Non-UUID string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot resolve test reference"):
            test_set._resolve_test_id("not-a-uuid")

    def test_resolve_test_instance_no_id_raises(self, test_set):
        """Test instance without id raises ValueError."""
        t = Test(category="Safety", behavior="Compliance")
        with pytest.raises(ValueError, match="Cannot resolve test reference"):
            test_set._resolve_test_id(t)


# ================================================================
# Tests for add_tests()
# ================================================================


class TestAddTests:
    """Tests for TestSet.add_tests()."""

    @patch("requests.request")
    def test_add_tests_by_instance(self, mock_request, test_set):
        """Test instances are resolved to their IDs."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "total_tests": 2,
            "message": "Associated 2 tests",
        }
        mock_request.return_value = mock_response

        t1 = Test(id="t-1", category="Safety", behavior="B1")
        t2 = Test(id="t-2", category="Safety", behavior="B2")
        result = test_set.add_tests([t1, t2])

        assert result is not None
        assert result["success"] is True

        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "POST"
        assert kwargs["url"] == "http://test:8000/test_sets/ts-111/associate"
        assert kwargs["json"] == {"test_ids": ["t-1", "t-2"]}

    @patch("requests.request")
    def test_add_tests_by_uuid(self, mock_request, test_set):
        """UUID strings are passed directly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "total_tests": 1,
            "message": "Associated 1 test",
        }
        mock_request.return_value = mock_response

        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        test_set.add_tests([uuid])

        _, kwargs = mock_request.call_args
        assert kwargs["json"] == {"test_ids": [uuid]}

    @patch("requests.request")
    def test_add_tests_by_dict(self, mock_request, test_set):
        """Dicts with 'id' key are resolved."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "total_tests": 1,
            "message": "ok",
        }
        mock_request.return_value = mock_response

        test_set.add_tests([{"id": "t-99"}])

        _, kwargs = mock_request.call_args
        assert kwargs["json"] == {"test_ids": ["t-99"]}

    @patch("requests.request")
    def test_add_tests_mixed_references(self, mock_request, test_set):
        """Mix of instances, dicts, and UUIDs in one call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "total_tests": 3,
            "message": "ok",
        }
        mock_request.return_value = mock_response

        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        t = Test(id="t-1", category="Safety", behavior="B")
        test_set.add_tests([t, {"id": "t-2"}, uuid])

        _, kwargs = mock_request.call_args
        assert kwargs["json"] == {"test_ids": ["t-1", "t-2", uuid]}

    @patch("requests.request")
    def test_add_tests_single_api_call(self, mock_request, test_set):
        """All test IDs are sent in a single bulk request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_request.return_value = mock_response

        t1 = Test(id="t-1", category="Safety", behavior="B1")
        t2 = Test(id="t-2", category="Safety", behavior="B2")
        test_set.add_tests([t1, t2])

        assert mock_request.call_count == 1

    def test_add_tests_no_id_raises(self, test_set_no_id):
        """ValueError when test set has no ID."""
        t = Test(id="t-1", category="Safety", behavior="B")
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.add_tests([t])

    def test_add_tests_invalid_ref_raises(self, test_set):
        """ValueError when a test reference cannot be resolved."""
        with pytest.raises(ValueError, match="Cannot resolve test reference"):
            test_set.add_tests(["not-a-uuid"])


# ================================================================
# Tests for remove_tests()
# ================================================================


class TestRemoveTests:
    """Tests for TestSet.remove_tests()."""

    @patch("requests.request")
    def test_remove_tests_by_instance(self, mock_request, test_set):
        """Test instances are resolved to their IDs for disassociation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "total_tests": 1,
            "removed_associations": 1,
            "message": "Removed 1 association",
        }
        mock_request.return_value = mock_response

        t = Test(id="t-1", category="Safety", behavior="B")
        result = test_set.remove_tests([t])

        assert result is not None
        assert result["success"] is True
        assert result["removed_associations"] == 1

        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "POST"
        assert kwargs["url"] == "http://test:8000/test_sets/ts-111/disassociate"
        assert kwargs["json"] == {"test_ids": ["t-1"]}

    @patch("requests.request")
    def test_remove_tests_by_uuid(self, mock_request, test_set):
        """UUID strings are passed directly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "total_tests": 1,
            "removed_associations": 1,
            "message": "ok",
        }
        mock_request.return_value = mock_response

        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        test_set.remove_tests([uuid])

        _, kwargs = mock_request.call_args
        assert kwargs["json"] == {"test_ids": [uuid]}

    @patch("requests.request")
    def test_remove_tests_single_api_call(self, mock_request, test_set):
        """All test IDs are sent in a single bulk request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_request.return_value = mock_response

        t1 = Test(id="t-1", category="Safety", behavior="B1")
        t2 = Test(id="t-2", category="Safety", behavior="B2")
        test_set.remove_tests([t1, t2])

        assert mock_request.call_count == 1
        _, kwargs = mock_request.call_args
        assert kwargs["json"] == {"test_ids": ["t-1", "t-2"]}

    def test_remove_tests_no_id_raises(self, test_set_no_id):
        """ValueError when test set has no ID."""
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.remove_tests(["t-1"])

    def test_remove_tests_invalid_ref_raises(self, test_set):
        """ValueError when a test reference cannot be resolved."""
        with pytest.raises(ValueError, match="Cannot resolve test reference"):
            test_set.remove_tests(["not-a-uuid"])

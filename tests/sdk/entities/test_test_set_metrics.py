import os
from unittest.mock import MagicMock, patch

import pytest

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
# Tests for get_metrics()
# ================================================================


class TestGetMetrics:
    """Tests for TestSet.get_metrics()."""

    @patch("requests.request")
    def test_get_metrics(self, mock_request, test_set):
        """Returns list of metric dicts."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "m-1", "name": "Accuracy"},
            {"id": "m-2", "name": "Toxicity"},
        ]
        mock_request.return_value = mock_response

        result = test_set.get_metrics()

        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "Accuracy"

        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "GET"
        assert kwargs["url"] == "http://test:8000/test_sets/ts-111/metrics"

    @patch("requests.request")
    def test_get_metrics_empty(self, mock_request, test_set):
        """Returns empty list when no metrics assigned."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        result = test_set.get_metrics()

        assert result == []

    def test_get_metrics_no_id_raises(self, test_set_no_id):
        """ValueError when test set has no ID."""
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.get_metrics()


# ================================================================
# Tests for add_metric()
# ================================================================


class TestAddMetric:
    """Tests for TestSet.add_metric()."""

    @patch("requests.request")
    def test_add_metric_by_dict(self, mock_request, test_set):
        """Passes dict with 'id' key — extracts id for URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "m-1", "name": "Accuracy"}]
        mock_request.return_value = mock_response

        result = test_set.add_metric({"id": "m-1", "name": "Accuracy"})

        assert result is not None
        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "POST"
        assert kwargs["url"] == "http://test:8000/test_sets/ts-111/metrics/m-1"

    @patch("requests.request")
    def test_add_metric_by_uuid(self, mock_request, test_set):
        """UUID string is used directly."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "name": "Acc"}
        ]
        mock_request.return_value = mock_response

        metric_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        test_set.add_metric(metric_uuid)

        _, kwargs = mock_request.call_args
        assert kwargs["url"] == (f"http://test:8000/test_sets/ts-111/metrics/{metric_uuid}")

    @patch("requests.request")
    def test_add_metric_by_name(self, mock_request, test_set):
        """Name string triggers lookup then POST."""
        # First call: metric lookup
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = [{"id": "m-resolved", "name": "Toxicity"}]

        # Second call: add metric
        add_resp = MagicMock()
        add_resp.json.return_value = [{"id": "m-resolved", "name": "Toxicity"}]

        mock_request.side_effect = [lookup_resp, add_resp]

        test_set.add_metric("Toxicity")

        assert mock_request.call_count == 2

        # Lookup call
        first = mock_request.call_args_list[0]
        assert first[1]["method"] == "GET"
        assert first[1]["params"] == {"$filter": "name eq 'Toxicity'"}

        # Add call
        second = mock_request.call_args_list[1]
        assert second[1]["method"] == "POST"
        assert "m-resolved" in second[1]["url"]

    def test_add_metric_no_id_raises(self, test_set_no_id):
        """ValueError when test set has no ID."""
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.add_metric("Accuracy")

    def test_add_metric_dict_missing_id_raises(self, test_set):
        """ValueError when dict has no 'id' key."""
        with pytest.raises(ValueError, match="Metric dict must contain an 'id' key"):
            test_set.add_metric({"name": "Accuracy"})


# ================================================================
# Tests for add_metrics()
# ================================================================


class TestAddMetrics:
    """Tests for TestSet.add_metrics()."""

    @patch("requests.request")
    def test_add_metrics_list(self, mock_request, test_set):
        """Each metric is added sequentially."""
        resp = MagicMock()
        resp.json.return_value = [
            {"id": "m-1", "name": "Accuracy"},
            {"id": "m-2", "name": "Toxicity"},
        ]
        mock_request.return_value = resp

        result = test_set.add_metrics(
            [
                {"id": "m-1", "name": "Accuracy"},
                {"id": "m-2", "name": "Toxicity"},
            ]
        )

        assert result is not None
        # Two POST calls
        assert mock_request.call_count == 2


# ================================================================
# Tests for remove_metric()
# ================================================================


class TestRemoveMetric:
    """Tests for TestSet.remove_metric()."""

    @patch("requests.request")
    def test_remove_metric_by_id(self, mock_request, test_set):
        """UUID string triggers DELETE with correct URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        metric_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        test_set.remove_metric(metric_uuid)

        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "DELETE"
        assert kwargs["url"] == (f"http://test:8000/test_sets/ts-111/metrics/{metric_uuid}")

    @patch("requests.request")
    def test_remove_metric_by_name(self, mock_request, test_set):
        """Name string triggers lookup then DELETE."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = [{"id": "m-resolved", "name": "Toxicity"}]

        delete_resp = MagicMock()
        delete_resp.json.return_value = []

        mock_request.side_effect = [lookup_resp, delete_resp]

        test_set.remove_metric("Toxicity")

        assert mock_request.call_count == 2
        second = mock_request.call_args_list[1]
        assert second[1]["method"] == "DELETE"
        assert "m-resolved" in second[1]["url"]

    def test_remove_metric_no_id_raises(self, test_set_no_id):
        """ValueError when test set has no ID."""
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.remove_metric("Accuracy")


# ================================================================
# Tests for remove_metrics()
# ================================================================


class TestRemoveMetrics:
    """Tests for TestSet.remove_metrics()."""

    @patch("requests.request")
    def test_remove_metrics_list(self, mock_request, test_set):
        """Each metric is removed sequentially."""
        resp = MagicMock()
        resp.json.return_value = []
        mock_request.return_value = resp

        result = test_set.remove_metrics(
            [
                {"id": "m-1", "name": "Accuracy"},
                {"id": "m-2", "name": "Toxicity"},
            ]
        )

        assert result is not None
        # Two DELETE calls
        assert mock_request.call_count == 2

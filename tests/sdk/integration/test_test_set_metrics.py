"""Integration tests for TestSet metric management methods.

These tests require a running backend (via docker-compose) and
exercise the full HTTP path: SDK -> backend API -> database.
"""

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.test_set import TestSet

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _create_metric(name: str) -> dict:
    """Create a metric via the backend API and return its dict."""
    client = APIClient()
    return client.send_request(
        endpoint=Endpoints.METRICS,
        method=Methods.POST,
        data={
            "name": name,
            "description": f"Integration test metric: {name}",
            "evaluation_prompt": "Rate the response.",
            "score_type": "numeric",
            "min_score": 0,
            "max_score": 1,
            "threshold": 0.5,
        },
    )


def _create_test_set(name: str = "Metric Mgmt Test Set") -> TestSet:
    """Create a minimal test set via the bulk endpoint."""
    ts = TestSet(
        name=name,
        description="Integration test set for metric management",
        short_description="Test",
        tests=[
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Compliance",
                "prompt": {"content": "Hello, is this safe?"},
            }
        ],
    )
    ts.push()
    assert ts.id is not None, "Test set creation failed"
    return ts


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestGetMetrics:
    def test_get_metrics_empty(self, db_cleanup):
        """New test set has no metrics."""
        ts = _create_test_set()
        result = ts.get_metrics()
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_metrics_after_adding(self, db_cleanup):
        """After adding a metric, get_metrics returns it."""
        ts = _create_test_set()
        metric = _create_metric("IntegrationAccuracy")

        ts.add_metric({"id": str(metric["id"])})

        result = ts.get_metrics()
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "IntegrationAccuracy"


class TestAddMetric:
    def test_add_metric_by_id(self, db_cleanup):
        """Add metric using its UUID string."""
        ts = _create_test_set()
        metric = _create_metric("AddById")

        result = ts.add_metric(str(metric["id"]))

        assert result is not None
        names = [m["name"] for m in result]
        assert "AddById" in names

    def test_add_metric_by_name(self, db_cleanup):
        """Add metric using its name (SDK resolves to ID)."""
        ts = _create_test_set()
        _create_metric("AddByName")

        result = ts.add_metric("AddByName")

        assert result is not None
        names = [m["name"] for m in result]
        assert "AddByName" in names

    def test_add_metric_by_dict(self, db_cleanup):
        """Add metric using a dict with 'id' key."""
        ts = _create_test_set()
        metric = _create_metric("AddByDict")

        result = ts.add_metric({"id": str(metric["id"])})

        assert result is not None
        names = [m["name"] for m in result]
        assert "AddByDict" in names


class TestAddMetrics:
    def test_add_metrics_list(self, db_cleanup):
        """Add multiple metrics in one call."""
        ts = _create_test_set()
        m1 = _create_metric("ListMetric1")
        m2 = _create_metric("ListMetric2")

        result = ts.add_metrics(
            [
                str(m1["id"]),
                str(m2["id"]),
            ]
        )

        assert result is not None
        names = [m["name"] for m in result]
        assert "ListMetric1" in names
        assert "ListMetric2" in names


class TestRemoveMetric:
    def test_remove_metric_by_id(self, db_cleanup):
        """Remove a metric by its UUID string."""
        ts = _create_test_set()
        metric = _create_metric("RemoveById")
        ts.add_metric(str(metric["id"]))

        result = ts.remove_metric(str(metric["id"]))

        assert result is not None
        assert len(result) == 0

    def test_remove_metric_by_name(self, db_cleanup):
        """Remove a metric by its name."""
        ts = _create_test_set()
        _create_metric("RemoveByName")
        ts.add_metric("RemoveByName")

        result = ts.remove_metric("RemoveByName")

        assert result is not None
        assert len(result) == 0


class TestRemoveMetrics:
    def test_remove_metrics_list(self, db_cleanup):
        """Remove multiple metrics in one call."""
        ts = _create_test_set()
        m1 = _create_metric("RemoveList1")
        m2 = _create_metric("RemoveList2")
        ts.add_metrics([str(m1["id"]), str(m2["id"])])

        result = ts.remove_metrics([str(m1["id"]), str(m2["id"])])

        assert result is not None
        assert len(result) == 0


class TestEdgeCases:
    def test_get_metrics_after_remove_all(self, db_cleanup):
        """After removing all metrics, get_metrics returns empty."""
        ts = _create_test_set()
        metric = _create_metric("Temporary")
        ts.add_metric(str(metric["id"]))
        ts.remove_metric(str(metric["id"]))

        result = ts.get_metrics()
        assert result is not None
        assert len(result) == 0

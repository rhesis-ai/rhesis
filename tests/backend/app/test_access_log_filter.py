"""Tests for the uvicorn access-log probe filter."""

import logging

import pytest

from rhesis.backend.logging.logging_config import _QuietProbeAccessFilter


def _access_record(path: str, status: int, method: str = "GET") -> logging.LogRecord:
    """A record shaped the way uvicorn emits access lines."""
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("10.3.3.1:52048", method, path, "1.1", status),
        exc_info=None,
    )


class TestQuietProbeAccessFilter:
    @pytest.fixture
    def probe_filter(self) -> _QuietProbeAccessFilter:
        return _QuietProbeAccessFilter()

    @pytest.mark.parametrize("path", ["/health", "/healthz"])
    @pytest.mark.parametrize("status", [200, 204, 301])
    def test_drops_successful_probes(self, probe_filter, path, status):
        assert probe_filter.filter(_access_record(path, status)) is False

    @pytest.mark.parametrize("status", [404, 500, 503])
    def test_keeps_failing_probes(self, probe_filter, status):
        """A probe that fails is the signal the filter exists to preserve."""
        assert probe_filter.filter(_access_record("/health", status)) is True

    @pytest.mark.parametrize("path", ["/tests", "/auth/providers", "/health/basic"])
    def test_keeps_other_paths(self, probe_filter, path):
        assert probe_filter.filter(_access_record(path, 200)) is True

    def test_drops_probe_with_query_string(self, probe_filter):
        assert probe_filter.filter(_access_record("/health?verbose=1", 200)) is False

    def test_keeps_non_access_records(self, probe_filter):
        """Only uvicorn's 5-arg access line is understood; anything else passes."""
        record = logging.LogRecord(
            name="rhesis.backend.app.main",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Health check called for /health",
            args=None,
            exc_info=None,
        )
        assert probe_filter.filter(record) is True

    def test_keeps_record_with_unexpected_arg_shape(self, probe_filter):
        """A uvicorn format change must degrade to logging everything."""
        record = _access_record("/health", 200)
        record.args = ("10.3.3.1:52048", "GET", "/health", "1.1", 200, "0.5ms")
        assert probe_filter.filter(record) is True

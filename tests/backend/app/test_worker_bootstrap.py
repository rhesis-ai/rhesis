"""Tests for the Celery worker bootstrap path.

The signal handler ``install_worker_usage_sink`` must install EE providers
(when the EE package is importable) **and** the usage sink. These tests
verify both halves without needing a live Celery worker.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rhesis.backend.app.ee_bootstrap import bootstrap_ee_providers


class TestBootstrapEeProviders:
    def test_installs_providers_when_ee_importable(self):
        mock_providers = MagicMock()
        with patch.dict(
            "sys.modules",
            {"rhesis.backend.ee": MagicMock(bootstrap_providers=mock_providers)},
        ):
            bootstrap_ee_providers()

        mock_providers.assert_called_once()

    def test_noop_when_ee_not_importable(self):
        with patch.dict("sys.modules", {"rhesis.backend.ee": None}):
            bootstrap_ee_providers()


class TestInstallWorkerUsageSink:
    def test_signal_handler_calls_both_bootstrap_and_sink(self):
        with (
            patch(
                "rhesis.backend.app.ee_bootstrap.bootstrap_ee_providers"
            ) as mock_providers,
            patch(
                "rhesis.backend.app.utils.usage_tracking.install_usage_sink"
            ) as mock_sink,
        ):
            from rhesis.backend.celery.signals import install_worker_usage_sink

            install_worker_usage_sink(sender=None)

        mock_providers.assert_called_once()
        mock_sink.assert_called_once()

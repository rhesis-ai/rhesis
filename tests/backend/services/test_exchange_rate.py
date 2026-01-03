"""Tests for exchange rate service."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from rhesis.backend.app.services.exchange_rate import ExchangeRateService


class TestExchangeRateService:
    """Test exchange rate service."""

    def test_fetch_rate_from_api_success(self, mocker):
        """Test successful API fetch."""
        # Mock httpx response
        mock_response = Mock()
        mock_response.json.return_value = {"rates": {"EUR": 0.92}}
        mock_response.raise_for_status = Mock()

        mocker.patch(
            "rhesis.backend.app.services.exchange_rate.httpx.get", return_value=mock_response
        )

        service = ExchangeRateService()
        rate = service._fetch_rate_from_api()

        assert rate == 0.92

    def test_fetch_rate_from_api_failure(self, mocker):
        """Test API fetch failure."""
        import httpx

        mocker.patch(
            "rhesis.backend.app.services.exchange_rate.httpx.get",
            side_effect=httpx.HTTPError("Network error"),
        )

        service = ExchangeRateService()
        rate = service._fetch_rate_from_api()

        assert rate is None

    def test_cache_validity(self):
        """Test cache validity checking."""
        service = ExchangeRateService()

        # No cache initially
        assert not service._is_cache_valid()

        # Set cache
        service._usd_to_eur_rate = 0.92
        service._last_fetch = datetime.utcnow()

        # Should be valid
        assert service._is_cache_valid()

        # Expire cache
        service._last_fetch = datetime.utcnow() - timedelta(hours=25)

        # Should be invalid
        assert not service._is_cache_valid()

    def test_get_rate_uses_cache(self, mocker):
        """Test that cached rate is used when valid."""
        service = ExchangeRateService()

        # Set valid cache
        service._usd_to_eur_rate = 0.95
        service._last_fetch = datetime.utcnow()

        # Mock API to verify it's not called
        mock_fetch = mocker.patch.object(service, "_fetch_rate_from_api")

        rate = service.get_usd_to_eur_rate()

        assert rate == 0.95
        mock_fetch.assert_not_called()

    def test_get_rate_fetches_when_cache_stale(self, mocker):
        """Test that fresh rate is fetched when cache is stale."""
        service = ExchangeRateService()

        # Set stale cache
        service._usd_to_eur_rate = 0.95
        service._last_fetch = datetime.utcnow() - timedelta(hours=25)

        # Mock API to return new rate
        mocker.patch.object(service, "_fetch_rate_from_api", return_value=0.93)

        rate = service.get_usd_to_eur_rate()

        assert rate == 0.93
        assert service._usd_to_eur_rate == 0.93

    def test_get_rate_uses_stale_cache_on_api_failure(self, mocker):
        """Test fallback to stale cache when API fails."""
        service = ExchangeRateService()

        # Set stale cache
        service._usd_to_eur_rate = 0.95
        service._last_fetch = datetime.utcnow() - timedelta(hours=25)

        # Mock API failure
        mocker.patch.object(service, "_fetch_rate_from_api", return_value=None)

        rate = service.get_usd_to_eur_rate()

        # Should use stale cache
        assert rate == 0.95

    def test_get_rate_uses_fallback_when_no_cache(self, mocker):
        """Test fallback to env var / default when no cache and API fails."""
        service = ExchangeRateService()

        # No cache
        assert service._usd_to_eur_rate is None

        # Mock API failure
        mocker.patch.object(service, "_fetch_rate_from_api", return_value=None)

        # Mock env var
        mocker.patch("os.getenv", return_value="0.88")

        rate = service.get_usd_to_eur_rate()

        # Should use env var fallback
        assert rate == 0.88

    def test_refresh_rate(self, mocker):
        """Test manual refresh."""
        service = ExchangeRateService()

        # Set initial cache
        service._usd_to_eur_rate = 0.95
        service._last_fetch = datetime.utcnow()

        # Mock API to return new rate
        mocker.patch.object(service, "_fetch_rate_from_api", return_value=0.93)

        # Refresh
        service.refresh_rate()

        # Should have new rate
        assert service._usd_to_eur_rate == 0.93

    @pytest.mark.asyncio
    async def test_fetch_rate_from_api_async_success(self, mocker):
        """Test successful async API fetch."""
        # Mock httpx async response
        mock_response = Mock()
        mock_response.json.return_value = {"rates": {"EUR": 0.92}}
        mock_response.raise_for_status = Mock()

        # Mock AsyncClient context manager
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value = mock_client

        mocker.patch(
            "rhesis.backend.app.services.exchange_rate.httpx.AsyncClient",
            return_value=mock_async_client,
        )

        service = ExchangeRateService()
        rate = await service._fetch_rate_from_api_async()

        assert rate == 0.92

    @pytest.mark.asyncio
    async def test_fetch_rate_from_api_async_failure(self, mocker):
        """Test async API fetch failure."""
        import httpx

        # Mock AsyncClient context manager with failure
        mock_client = Mock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Network error"))
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value = mock_client

        mocker.patch(
            "rhesis.backend.app.services.exchange_rate.httpx.AsyncClient",
            return_value=mock_async_client,
        )

        service = ExchangeRateService()
        rate = await service._fetch_rate_from_api_async()

        assert rate is None

    @pytest.mark.asyncio
    async def test_get_rate_async_uses_cache(self, mocker):
        """Test that cached rate is used in async version when valid."""
        service = ExchangeRateService()

        # Set valid cache
        service._usd_to_eur_rate = 0.95
        service._last_fetch = datetime.utcnow()

        # Mock async API to verify it's not called
        mock_fetch = mocker.patch.object(service, "_fetch_rate_from_api_async")

        rate = await service.get_usd_to_eur_rate_async()

        assert rate == 0.95
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_rate_async_fetches_when_cache_stale(self, mocker):
        """Test that fresh rate is fetched asynchronously when cache is stale."""
        service = ExchangeRateService()

        # Set stale cache
        service._usd_to_eur_rate = 0.95
        service._last_fetch = datetime.utcnow() - timedelta(hours=25)

        # Mock async API to return new rate
        mocker.patch.object(service, "_fetch_rate_from_api_async", return_value=0.93)

        rate = await service.get_usd_to_eur_rate_async()

        assert rate == 0.93
        assert service._usd_to_eur_rate == 0.93

    @pytest.mark.asyncio
    async def test_get_rate_async_uses_stale_cache_on_api_failure(self, mocker):
        """Test async version fallback to stale cache when API fails."""
        service = ExchangeRateService()

        # Set stale cache
        service._usd_to_eur_rate = 0.95
        service._last_fetch = datetime.utcnow() - timedelta(hours=25)

        # Mock async API failure
        mocker.patch.object(service, "_fetch_rate_from_api_async", return_value=None)

        rate = await service.get_usd_to_eur_rate_async()

        # Should use stale cache
        assert rate == 0.95

    @pytest.mark.asyncio
    async def test_get_rate_async_uses_fallback_when_no_cache(self, mocker):
        """Test async version fallback to env var / default when no cache and API fails."""
        service = ExchangeRateService()

        # No cache
        assert service._usd_to_eur_rate is None

        # Mock async API failure
        mocker.patch.object(service, "_fetch_rate_from_api_async", return_value=None)

        # Mock env var
        mocker.patch("os.getenv", return_value="0.88")

        rate = await service.get_usd_to_eur_rate_async()

        # Should use env var fallback
        assert rate == 0.88

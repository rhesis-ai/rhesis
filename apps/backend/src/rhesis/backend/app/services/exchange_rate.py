"""Exchange rate service for currency conversions.

Fetches current exchange rates from Frankfurter API (free, no API key required).
Caches rates for 24 hours and provides fallback to environment variable or default.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Service for fetching and caching exchange rates."""

    def __init__(self):
        """Initialize the exchange rate service."""
        self._usd_to_eur_rate: Optional[float] = None
        self._last_fetch: Optional[datetime] = None
        self._cache_duration = timedelta(hours=24)
        self._api_url = "https://api.frankfurter.app/latest"

    def get_usd_to_eur_rate(self) -> float:
        """
        Get the current USD to EUR exchange rate.

        Fetches from API if cache is stale, otherwise returns cached value.
        Falls back to environment variable or default if API fails.

        Returns:
            Exchange rate (EUR per USD)
        """
        # Check if cache is valid
        if self._is_cache_valid():
            logger.debug(f"Using cached exchange rate: {self._usd_to_eur_rate}")
            return self._usd_to_eur_rate

        # Try to fetch fresh rate
        try:
            rate = self._fetch_rate_from_api()
            if rate:
                self._usd_to_eur_rate = rate
                self._last_fetch = datetime.utcnow()
                logger.info(f"Fetched fresh exchange rate: 1 USD = {rate:.4f} EUR")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rate from API: {e}")

        # Fallback to cached rate (even if stale)
        if self._usd_to_eur_rate:
            logger.info(f"Using stale cached rate due to API failure: {self._usd_to_eur_rate}")
            return self._usd_to_eur_rate

        # Final fallback to env var or default
        fallback_rate = float(os.getenv("USD_TO_EUR_RATE", "0.92"))
        logger.warning(
            f"No cached rate available, using fallback: {fallback_rate} "
            "(from USD_TO_EUR_RATE env var or default)"
        )
        return fallback_rate

    def _is_cache_valid(self) -> bool:
        """Check if cached exchange rate is still valid."""
        if not self._usd_to_eur_rate or not self._last_fetch:
            return False

        age = datetime.utcnow() - self._last_fetch
        return age < self._cache_duration

    def _fetch_rate_from_api(self) -> Optional[float]:
        """
        Fetch exchange rate from Frankfurter API (synchronous).

        Returns:
            Exchange rate or None if fetch fails
        """
        try:
            # Fetch latest rates from USD
            response = httpx.get(
                self._api_url,
                params={"from": "USD", "to": "EUR"},
                timeout=5.0,
            )
            response.raise_for_status()

            data = response.json()
            rate = data.get("rates", {}).get("EUR")

            if rate:
                return float(rate)
            else:
                logger.error(f"Unexpected API response format: {data}")
                return None

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching exchange rate: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing exchange rate response: {e}")
            return None

    async def _fetch_rate_from_api_async(self) -> Optional[float]:
        """
        Fetch exchange rate from Frankfurter API (asynchronous).

        Returns:
            Exchange rate or None if fetch fails
        """
        try:
            # Use async client for non-blocking HTTP request
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self._api_url,
                    params={"from": "USD", "to": "EUR"},
                    timeout=5.0,
                )
                response.raise_for_status()

                data = response.json()
                rate = data.get("rates", {}).get("EUR")

                if rate:
                    return float(rate)
                else:
                    logger.error(f"Unexpected API response format: {data}")
                    return None

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching exchange rate: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing exchange rate response: {e}")
            return None

    async def get_usd_to_eur_rate_async(self) -> float:
        """
        Get the current USD to EUR exchange rate (asynchronous).

        Fetches from API if cache is stale, otherwise returns cached value.
        Falls back to environment variable or default if API fails.

        This method should be used in async contexts to avoid blocking the event loop.

        Returns:
            Exchange rate (EUR per USD)
        """
        # Check if cache is valid
        if self._is_cache_valid():
            logger.debug(f"Using cached exchange rate: {self._usd_to_eur_rate}")
            return self._usd_to_eur_rate

        # Try to fetch fresh rate
        try:
            rate = await self._fetch_rate_from_api_async()
            if rate:
                self._usd_to_eur_rate = rate
                self._last_fetch = datetime.utcnow()
                logger.info(f"Fetched fresh exchange rate: 1 USD = {rate:.4f} EUR")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rate from API: {e}")

        # Fallback to cached rate (even if stale)
        if self._usd_to_eur_rate:
            logger.info(f"Using stale cached rate due to API failure: {self._usd_to_eur_rate}")
            return self._usd_to_eur_rate

        # Final fallback to env var or default
        fallback_rate = float(os.getenv("USD_TO_EUR_RATE", "0.92"))
        logger.warning(
            f"No cached rate available, using fallback: {fallback_rate} "
            "(from USD_TO_EUR_RATE env var or default)"
        )
        return fallback_rate

    def refresh_rate(self) -> None:
        """
        Force refresh the exchange rate from API.

        Useful for manual refresh or scheduled jobs.
        """
        logger.info("Manually refreshing exchange rate...")
        self._last_fetch = None  # Invalidate cache
        self.get_usd_to_eur_rate()


# Global singleton instance
_exchange_rate_service = ExchangeRateService()


def get_exchange_rate_service() -> ExchangeRateService:
    """Get the global exchange rate service instance."""
    return _exchange_rate_service


def get_usd_to_eur_rate() -> float:
    """
    Convenience function to get USD to EUR exchange rate (synchronous).

    Returns:
        Exchange rate (EUR per USD)
    """
    return _exchange_rate_service.get_usd_to_eur_rate()


async def get_usd_to_eur_rate_async() -> float:
    """
    Convenience function to get USD to EUR exchange rate (asynchronous).

    Use this in async contexts to avoid blocking the event loop.

    Returns:
        Exchange rate (EUR per USD)
    """
    return await _exchange_rate_service.get_usd_to_eur_rate_async()

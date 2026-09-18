"""Exchange rates for showing costs in a currency other than the stored one.

Rates come from the Frankfurter API (free, no API key), which republishes
European Central Bank reference rates. The ECB sets those once per working day,
so these are daily figures rather than real-time ones -- the right granularity
for costs measured in fractions of a cent.

Fetched for every convertible currency at once and cached 24 hours in process,
with a chain of fallbacks so an instance behind a firewall still shows
something: the live fetch, then the last rates seen however stale, then the
``USD_TO_EUR_RATE`` env var. That last one covers EUR only, which is all it ever
covered; a currency with no rate is simply absent, and callers show the base
currency rather than invent a conversion.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

import httpx

from rhesis.backend.app.constants_currency import BASE_CURRENCY, CONVERTIBLE_CURRENCIES

logger = logging.getLogger(__name__)

#: Used when the API has never been reached and no rate was ever cached.
_EUR_FALLBACK_ENV = "USD_TO_EUR_RATE"
_EUR_FALLBACK_DEFAULT = "0.92"

_API_URL = "https://api.frankfurter.dev/v1/latest"


@dataclass(frozen=True)
class RateSnapshot:
    """Rates per one unit of the base currency, and the day they are from.

    ``as_of`` is None for the env-var fallback, which has no date behind it --
    callers say the rate's age is unknown rather than implying it is today's.
    """

    rates: Dict[str, float] = field(default_factory=dict)
    as_of: Optional[date] = None

    def rate_for(self, currency: str) -> Optional[float]:
        if currency == BASE_CURRENCY.value:
            return 1.0
        return self.rates.get(currency)


def _parse(payload: dict) -> Optional[RateSnapshot]:
    """Turn a Frankfurter response into a snapshot, or None if it made no sense."""
    rates = payload.get("rates")
    if not isinstance(rates, dict) or not rates:
        logger.error(f"Unexpected exchange rate response: {payload}")
        return None

    parsed: Dict[str, float] = {}
    for currency, value in rates.items():
        try:
            parsed[currency] = float(value)
        except (TypeError, ValueError):
            logger.warning(f"Skipping unparseable rate for {currency}: {value!r}")

    if not parsed:
        return None

    as_of = None
    raw_date = payload.get("date")
    if isinstance(raw_date, str):
        try:
            as_of = date.fromisoformat(raw_date)
        except ValueError:
            logger.warning(f"Unparseable rate date: {raw_date!r}")

    return RateSnapshot(rates=parsed, as_of=as_of)


def _configured_eur_rate() -> float:
    """The EUR rate from the environment, or the built-in default.

    Parsed defensively because this is the bottom of the fallback chain: a
    misconfigured value here would otherwise raise out of a request whose whole
    purpose is to always return something.
    """
    raw = os.getenv(_EUR_FALLBACK_ENV)
    if raw is None:
        return float(_EUR_FALLBACK_DEFAULT)
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        logger.error(f"{_EUR_FALLBACK_ENV} is not a number ({raw!r}); using the default")
        return float(_EUR_FALLBACK_DEFAULT)
    if rate <= 0:
        logger.error(f"{_EUR_FALLBACK_ENV} must be positive ({rate}); using the default")
        return float(_EUR_FALLBACK_DEFAULT)
    return rate


def _env_fallback() -> RateSnapshot:
    """EUR from the env var, for an instance that has never reached the API."""
    rate = _configured_eur_rate()
    logger.warning(
        f"No exchange rates available, falling back to {rate} EUR per USD "
        f"(from {_EUR_FALLBACK_ENV} or its default). Other currencies are unavailable."
    )
    return RateSnapshot(rates={"EUR": rate}, as_of=None)


class ExchangeRateService:
    """Fetches and caches rates for every convertible currency."""

    def __init__(self):
        self._snapshot: Optional[RateSnapshot] = None
        self._last_fetch: Optional[datetime] = None
        self._cache_duration = timedelta(hours=24)
        self._api_url = _API_URL

    # -- reads ------------------------------------------------------------

    def get_rates(self) -> RateSnapshot:
        """Current rates per one USD, fetching if the cache has gone stale."""
        if self._is_cache_valid():
            return self._snapshot

        try:
            snapshot = self._fetch()
            if snapshot:
                return self._store(snapshot)
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rates: {e}")

        return self._after_failed_fetch()

    async def get_rates_async(self) -> RateSnapshot:
        """Same, without blocking the event loop."""
        if self._is_cache_valid():
            return self._snapshot

        try:
            snapshot = await self._fetch_async()
            if snapshot:
                return self._store(snapshot)
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rates: {e}")

        return self._after_failed_fetch()

    def get_usd_to_eur_rate(self) -> float:
        """The EUR rate alone, which is what enrichment stores per trace."""
        return self.get_rates().rate_for("EUR") or _configured_eur_rate()

    async def get_usd_to_eur_rate_async(self) -> float:
        snapshot = await self.get_rates_async()
        return snapshot.rate_for("EUR") or _configured_eur_rate()

    def refresh_rate(self) -> None:
        """Force a refresh, for a manual or scheduled refetch."""
        logger.info("Manually refreshing exchange rates...")
        self._last_fetch = None
        self.get_rates()

    # -- internals --------------------------------------------------------

    def _store(self, snapshot: RateSnapshot) -> RateSnapshot:
        self._snapshot = snapshot
        self._last_fetch = datetime.now(timezone.utc)
        logger.info(f"Fetched exchange rates ({snapshot.as_of}): {snapshot.rates}")
        return snapshot

    def _after_failed_fetch(self) -> RateSnapshot:
        """Stale rates beat no rates; the env var beats nothing at all."""
        if self._snapshot:
            logger.info("Using stale cached exchange rates after a failed fetch")
            return self._snapshot

        # Cached so a firewalled instance does not retry the API on every call.
        return self._store(_env_fallback())

    def _is_cache_valid(self) -> bool:
        if not self._snapshot or not self._last_fetch:
            return False
        return datetime.now(timezone.utc) - self._last_fetch < self._cache_duration

    @property
    def _params(self) -> dict:
        return {"base": BASE_CURRENCY.value, "symbols": ",".join(CONVERTIBLE_CURRENCIES)}

    def _fetch(self) -> Optional[RateSnapshot]:
        try:
            response = httpx.get(
                self._api_url, params=self._params, timeout=2.0, follow_redirects=True
            )
            response.raise_for_status()
            return _parse(response.json())
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching exchange rates: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing exchange rate response: {e}")
            return None

    async def _fetch_async(self) -> Optional[RateSnapshot]:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(self._api_url, params=self._params, timeout=5.0)
                response.raise_for_status()
                return _parse(response.json())
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching exchange rates: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing exchange rate response: {e}")
            return None


_exchange_rate_service = ExchangeRateService()


def get_exchange_rate_service() -> ExchangeRateService:
    """The process-wide service instance."""
    return _exchange_rate_service


def get_rates() -> RateSnapshot:
    """Current rates per one USD."""
    return _exchange_rate_service.get_rates()


async def get_rates_async() -> RateSnapshot:
    return await _exchange_rate_service.get_rates_async()


def get_usd_to_eur_rate() -> float:
    """USD to EUR, as enrichment has always asked for it."""
    return _exchange_rate_service.get_usd_to_eur_rate()


async def get_usd_to_eur_rate_async() -> float:
    return await _exchange_rate_service.get_usd_to_eur_rate_async()

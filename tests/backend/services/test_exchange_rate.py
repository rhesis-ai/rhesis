"""Tests for the exchange rate service.

Two things are being guarded. Rates are fetched for every convertible currency
at once, so a caller can show any of them without a request each. And the
fallback chain never leaves a caller with nothing: live rates, else the last
rates seen however stale, else the configured EUR rate -- with a currency that
has no rate simply absent rather than guessed at.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from rhesis.backend.app.services.exchange_rate import ExchangeRateService, RateSnapshot

LIVE_PAYLOAD = {
    "base": "USD",
    "date": "2026-09-17",
    "rates": {"EUR": 0.871, "GBP": 0.74758, "CHF": 0.82449},
}


def fresh(rates: dict, as_of: date | None = None) -> RateSnapshot:
    return RateSnapshot(rates=rates, as_of=as_of)


def cached(service: ExchangeRateService, rates: dict, *, age_hours: float = 0) -> None:
    service._snapshot = fresh(rates)
    service._last_fetch = datetime.now(timezone.utc) - timedelta(hours=age_hours)


def mock_async_client(mocker, *, response=None, error=None):
    client = Mock()
    client.get = AsyncMock(side_effect=error) if error else AsyncMock(return_value=response)
    async_client = AsyncMock()
    async_client.__aenter__.return_value = client
    mocker.patch(
        "rhesis.backend.app.services.exchange_rate.httpx.AsyncClient",
        return_value=async_client,
    )


class TestSnapshot:
    """What a caller reads off the result."""

    def test_the_base_currency_is_always_one_of_itself(self):
        assert fresh({"EUR": 0.871}).rate_for("USD") == 1.0

    def test_a_currency_with_no_rate_is_absent_rather_than_guessed(self):
        # The caller shows the base currency; it must not invent a conversion.
        assert fresh({"EUR": 0.871}).rate_for("JPY") is None


class TestFetching:
    """One request covers every currency the product offers."""

    def test_asks_for_every_convertible_currency_at_once(self, mocker):
        response = Mock()
        response.json.return_value = LIVE_PAYLOAD
        response.raise_for_status = Mock()
        get = mocker.patch(
            "rhesis.backend.app.services.exchange_rate.httpx.get", return_value=response
        )

        ExchangeRateService()._fetch()

        params = get.call_args.kwargs["params"]
        assert params["base"] == "USD"
        assert set(params["symbols"].split(",")) == {"EUR", "GBP", "CHF"}

    def test_reads_every_rate_and_the_day_they_are_from(self, mocker):
        response = Mock()
        response.json.return_value = LIVE_PAYLOAD
        response.raise_for_status = Mock()
        mocker.patch("rhesis.backend.app.services.exchange_rate.httpx.get", return_value=response)

        snapshot = ExchangeRateService()._fetch()

        assert snapshot.rates == {"EUR": 0.871, "GBP": 0.74758, "CHF": 0.82449}
        assert snapshot.as_of == date(2026, 9, 17)

    def test_keeps_the_rates_it_can_parse(self, mocker):
        response = Mock()
        response.json.return_value = {"date": "2026-09-17", "rates": {"EUR": 0.871, "GBP": None}}
        response.raise_for_status = Mock()
        mocker.patch("rhesis.backend.app.services.exchange_rate.httpx.get", return_value=response)

        snapshot = ExchangeRateService()._fetch()

        # GBP is dropped rather than taking EUR down with it.
        assert snapshot.rates == {"EUR": 0.871}

    def test_an_undated_response_still_yields_rates(self, mocker):
        response = Mock()
        response.json.return_value = {"rates": {"EUR": 0.871}}
        response.raise_for_status = Mock()
        mocker.patch("rhesis.backend.app.services.exchange_rate.httpx.get", return_value=response)

        snapshot = ExchangeRateService()._fetch()

        assert snapshot.rates == {"EUR": 0.871}
        assert snapshot.as_of is None

    def test_a_network_failure_is_no_rates_rather_than_an_exception(self, mocker):
        import httpx

        mocker.patch(
            "rhesis.backend.app.services.exchange_rate.httpx.get",
            side_effect=httpx.HTTPError("Network error"),
        )

        assert ExchangeRateService()._fetch() is None

    def test_a_response_with_no_rates_is_treated_as_a_failure(self, mocker):
        response = Mock()
        response.json.return_value = {"date": "2026-09-17"}
        response.raise_for_status = Mock()
        mocker.patch("rhesis.backend.app.services.exchange_rate.httpx.get", return_value=response)

        assert ExchangeRateService()._fetch() is None


class TestCaching:
    """A day's cache, because the rates themselves change once a day."""

    def test_serves_the_cache_without_asking_again(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95})
        fetch = mocker.patch.object(service, "_fetch")

        assert service.get_rates().rates == {"EUR": 0.95}
        fetch.assert_not_called()

    def test_refetches_once_the_cache_is_a_day_old(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95}, age_hours=25)
        mocker.patch.object(service, "_fetch", return_value=fresh({"EUR": 0.93}))

        assert service.get_rates().rates == {"EUR": 0.93}

    def test_a_manual_refresh_ignores_a_valid_cache(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95})
        mocker.patch.object(service, "_fetch", return_value=fresh({"EUR": 0.93}))

        service.refresh_rate()

        assert service.get_rates().rates == {"EUR": 0.93}


class TestFallbacks:
    """Never leave the caller with nothing to convert by."""

    def test_stale_rates_beat_no_rates(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95, "GBP": 0.80}, age_hours=25)
        mocker.patch.object(service, "_fetch", return_value=None)

        assert service.get_rates().rates == {"EUR": 0.95, "GBP": 0.80}

    def test_falls_back_to_the_configured_rate_when_nothing_was_ever_cached(self, mocker):
        service = ExchangeRateService()
        mocker.patch.object(service, "_fetch", return_value=None)
        mocker.patch("os.getenv", return_value="0.88")

        snapshot = service.get_rates()

        assert snapshot.rate_for("EUR") == 0.88
        # No date, because a configured rate has no day behind it.
        assert snapshot.as_of is None

    def test_the_fallback_offers_no_currency_it_has_no_rate_for(self, mocker):
        service = ExchangeRateService()
        mocker.patch.object(service, "_fetch", return_value=None)
        mocker.patch("os.getenv", return_value="0.88")

        snapshot = service.get_rates()

        assert snapshot.rate_for("GBP") is None
        assert snapshot.rate_for("CHF") is None
        # The base is still convertible, so the UI has somewhere to land.
        assert snapshot.rate_for("USD") == 1.0

    def test_the_fallback_is_cached_so_a_firewalled_instance_stops_retrying(self, mocker):
        service = ExchangeRateService()
        fetch = mocker.patch.object(service, "_fetch", return_value=None)
        mocker.patch("os.getenv", return_value="0.88")

        service.get_rates()
        service.get_rates()

        assert fetch.call_count == 1


class TestMisconfiguredFallback:
    """The bottom of the chain must not raise; it is the last thing left."""

    @pytest.mark.parametrize("value", ["", "nonsense", "0", "-1", "1,2"])
    def test_an_unusable_configured_rate_falls_back_to_the_default(
        self, value, mocker, monkeypatch
    ):
        monkeypatch.setenv("USD_TO_EUR_RATE", value)
        service = ExchangeRateService()
        mocker.patch.object(service, "_fetch", return_value=None)

        snapshot = service.get_rates()

        assert snapshot.rate_for("EUR") == 0.92

    def test_a_usable_configured_rate_is_honoured(self, mocker, monkeypatch):
        monkeypatch.setenv("USD_TO_EUR_RATE", "0.88")
        service = ExchangeRateService()
        mocker.patch.object(service, "_fetch", return_value=None)

        assert service.get_rates().rate_for("EUR") == 0.88

    def test_the_endpoint_still_gets_rates_under_misconfiguration(self, mocker, monkeypatch):
        """What the guard is for: this used to raise out of the request."""
        monkeypatch.setenv("USD_TO_EUR_RATE", "not-a-number")
        service = ExchangeRateService()
        mocker.patch.object(service, "_fetch", return_value=None)

        snapshot = service.get_rates()

        assert snapshot.rates
        assert snapshot.rate_for("USD") == 1.0


class TestTheFallbackIsNotStickyForADay:
    """One missed fetch must not take three currencies off the menu until tomorrow."""

    def test_the_fallback_is_retried_within_minutes(self, mocker):
        service = ExchangeRateService()
        fetch = mocker.patch.object(service, "_fetch", return_value=None)
        service.get_rates()
        assert fetch.call_count == 1

        # Long past the fallback's own window, nowhere near the real one.
        service._last_fetch = datetime.now(timezone.utc) - timedelta(minutes=6)
        fetch.return_value = fresh({"EUR": 0.871, "GBP": 0.74758, "CHF": 0.82449})

        snapshot = service.get_rates()

        assert fetch.call_count == 2
        assert snapshot.rate_for("GBP") == 0.74758

    def test_real_rates_are_still_kept_for_the_day(self, mocker):
        service = ExchangeRateService()
        mocker.patch.object(service, "_fetch", return_value=fresh({"EUR": 0.871}))
        service.get_rates()

        service._last_fetch = datetime.now(timezone.utc) - timedelta(hours=6)
        fetch = mocker.patch.object(service, "_fetch")

        service.get_rates()

        fetch.assert_not_called()

    def test_the_fallback_still_holds_for_a_few_minutes(self, mocker):
        """It is a backstop against hammering the API, just not a day-long one."""
        service = ExchangeRateService()
        fetch = mocker.patch.object(service, "_fetch", return_value=None)

        service.get_rates()
        service.get_rates()

        assert fetch.call_count == 1


class TestOutageBackoff:
    """A provider outage must not put a network timeout on every request."""

    def test_stale_rates_are_served_without_retrying_every_time(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95, "GBP": 0.80}, age_hours=25)
        fetch = mocker.patch.object(service, "_fetch", return_value=None)

        first = service.get_rates()
        second = service.get_rates()

        # One attempt, not one per call -- the second is served from the same
        # stale snapshot rather than sitting on the provider's timeout again.
        assert fetch.call_count == 1
        assert first.rates == second.rates == {"EUR": 0.95, "GBP": 0.80}

    def test_it_tries_again_a_few_minutes_later(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95}, age_hours=25)
        fetch = mocker.patch.object(service, "_fetch", return_value=None)
        service.get_rates()

        service._last_fetch = datetime.now(timezone.utc) - timedelta(minutes=6)
        fetch.return_value = fresh({"EUR": 0.871, "GBP": 0.74758})

        snapshot = service.get_rates()

        assert fetch.call_count == 2
        assert snapshot.rate_for("GBP") == 0.74758

    def test_stale_rates_keep_the_day_they_are_actually_from(self, mocker):
        """Resetting the retry clock must not backdate the rates themselves."""
        service = ExchangeRateService()
        service._snapshot = fresh({"EUR": 0.95}, as_of=date(2026, 9, 10))
        service._last_fetch = datetime.now(timezone.utc) - timedelta(hours=25)
        mocker.patch.object(service, "_fetch", return_value=None)

        assert service.get_rates().as_of == date(2026, 9, 10)


class TestTheEurAccessorEnrichmentUses:
    """Enrichment asks for EUR by name, and must not notice any of this."""

    def test_returns_the_eur_rate_from_the_snapshot(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.871, "GBP": 0.74758})

        assert service.get_usd_to_eur_rate() == 0.871

    def test_falls_back_when_the_snapshot_has_no_eur(self, mocker):
        service = ExchangeRateService()
        cached(service, {"GBP": 0.74758})
        mocker.patch("os.getenv", return_value="0.88")

        assert service.get_usd_to_eur_rate() == 0.88


@pytest.mark.asyncio
class TestAsync:
    """The same behaviour off the event loop, for the request path."""

    async def test_reads_every_rate(self, mocker):
        response = Mock()
        response.json.return_value = LIVE_PAYLOAD
        response.raise_for_status = Mock()
        mock_async_client(mocker, response=response)

        snapshot = await ExchangeRateService()._fetch_async()

        assert snapshot.rates == {"EUR": 0.871, "GBP": 0.74758, "CHF": 0.82449}
        assert snapshot.as_of == date(2026, 9, 17)

    async def test_a_network_failure_is_no_rates(self, mocker):
        import httpx

        mock_async_client(mocker, error=httpx.HTTPError("Network error"))

        assert await ExchangeRateService()._fetch_async() is None

    async def test_serves_the_cache_without_asking_again(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95})
        fetch = mocker.patch.object(service, "_fetch_async")

        assert (await service.get_rates_async()).rates == {"EUR": 0.95}
        fetch.assert_not_called()

    async def test_refetches_once_the_cache_is_a_day_old(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95}, age_hours=25)
        mocker.patch.object(service, "_fetch_async", return_value=fresh({"EUR": 0.93}))

        assert (await service.get_rates_async()).rates == {"EUR": 0.93}

    async def test_stale_rates_beat_no_rates(self, mocker):
        service = ExchangeRateService()
        cached(service, {"EUR": 0.95}, age_hours=25)
        mocker.patch.object(service, "_fetch_async", return_value=None)

        assert (await service.get_rates_async()).rates == {"EUR": 0.95}

    async def test_falls_back_to_the_configured_rate(self, mocker):
        service = ExchangeRateService()
        mocker.patch.object(service, "_fetch_async", return_value=None)
        mocker.patch("os.getenv", return_value="0.88")

        assert await service.get_usd_to_eur_rate_async() == 0.88

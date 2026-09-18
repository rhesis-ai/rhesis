"""Tests for GET /services/exchange-rates.

The rates the UI converts stored costs by. The endpoint itself is thin; what it
has to get right is saying which currency the figures are *from*, and admitting
when it does not know how old they are.
"""

from datetime import date

import pytest
from fastapi import status

from rhesis.backend.app.services.exchange_rate import RateSnapshot

ENDPOINT = "/services/exchange-rates"
RATES = "rhesis.backend.app.services.exchange_rate.get_rates_async"


@pytest.fixture
def live_rates(mocker):
    async def _rates():
        return RateSnapshot(
            rates={"EUR": 0.871, "GBP": 0.74758, "CHF": 0.82449},
            as_of=date(2026, 9, 17),
        )

    return mocker.patch(RATES, side_effect=_rates)


class TestExchangeRates:
    def test_returns_a_rate_for_every_currency_offered(self, authenticated_client, live_rates):
        response = authenticated_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert set(response.json()["rates"]) == {"EUR", "GBP", "CHF"}

    def test_names_the_currency_the_rates_convert_from(self, authenticated_client, live_rates):
        """Without this the numbers are meaningless -- 0.871 of what, per what."""
        response = authenticated_client.get(ENDPOINT)

        assert response.json()["base"] == "USD"

    def test_reports_the_day_the_rates_are_from(self, authenticated_client, live_rates):
        response = authenticated_client.get(ENDPOINT)

        assert response.json()["as_of"] == "2026-09-17"

    def test_admits_when_the_age_of_the_rates_is_unknown(self, authenticated_client, mocker):
        """The configured fallback has no day behind it, so it claims none."""

        async def _fallback():
            return RateSnapshot(rates={"EUR": 0.92}, as_of=None)

        mocker.patch(RATES, side_effect=_fallback)

        response = authenticated_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["as_of"] is None
        assert response.json()["rates"] == {"EUR": 0.92}

    def test_requires_authentication(self, client, live_rates):
        response = client.get(ENDPOINT)

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

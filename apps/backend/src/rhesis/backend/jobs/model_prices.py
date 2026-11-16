"""Daily refresh of the model prices the hosted spend cap uses.

Every process loads litellm's price list once, at import. This job fetches the
current list, keeps our default models' entries and shares them through Redis,
so a long-running pod picks up a price change within a day
(``app/quota/hosted_spend.py``).
"""

import logging

from rhesis.backend.app.quota.hosted_spend import hosted_spend
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


@app.task(ignore_result=True)
def refresh_model_prices() -> int:
    """Returns how many model price entries were stored, for tests."""
    stored = hosted_spend.refresh_prices()
    logger.info("Refreshed hosted model prices: %d entries stored", stored)
    return stored

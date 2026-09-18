"""The currencies costs can be shown in.

USD is the stored figure: enrichment prices every span in it, and every other
currency is a conversion of that at the current rate. Adding one here is the
whole change -- no migration, since both the organization default and the user
override live in JSONB.
"""

from enum import Enum


class Currency(str, Enum):
    """A currency costs can be displayed in."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CHF = "CHF"


#: The currency every cost is stored and priced in.
BASE_CURRENCY = Currency.USD

#: Everything the rate service has to fetch, i.e. all but the base.
CONVERTIBLE_CURRENCIES = tuple(c.value for c in Currency if c is not BASE_CURRENCY)

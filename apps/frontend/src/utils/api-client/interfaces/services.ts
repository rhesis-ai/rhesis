import type { Currency, Rates } from '@/utils/money';

/**
 * Rates for converting a stored cost into another currency.
 *
 * Costs are stored in `base`; every other figure on screen is a multiplication
 * of one. A currency missing from `rates` has no rate available, and callers
 * show the base currency rather than guess at one.
 */
export interface ExchangeRatesResponse {
  base: Currency;
  rates: Rates;
  /** The business day the rates are from, or null when they came from the
   *  configured fallback and their age is unknown. */
  as_of: string | null;
}

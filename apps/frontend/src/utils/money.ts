/**
 * Showing a stored cost in the currency someone chose.
 *
 * USD is the record: enrichment prices every span in it, and every other
 * currency on screen is that figure converted at the current rate. The stored
 * EUR alongside it is frozen at whatever rate was cached when enrichment ran,
 * with no note of when -- reading it for EUR while converting live for GBP
 * would put two currencies on one screen on different bases.
 */

/** What the backend's Currency enum offers; kept in step with it by hand. */
export const CURRENCIES = ['USD', 'EUR', 'GBP', 'CHF'] as const;

export type Currency = (typeof CURRENCIES)[number];

/** The currency costs are stored and priced in. */
export const BASE_CURRENCY: Currency = 'USD';

/** Rates per one unit of the base currency, as the API reports them. */
export type Rates = Partial<Record<Currency, number>>;

export function isCurrency(value: unknown): value is Currency {
  return (
    typeof value === 'string' &&
    (CURRENCIES as readonly string[]).includes(value)
  );
}

/**
 * Decimals for a figure of this size, matching what costs have always shown:
 * two for ordinary money, more as the figure shrinks, because a cost of a
 * thousandth of a cent still has to say something other than zero.
 *
 * Read off the stored USD figure rather than the converted one, so the same
 * cost is written to the same precision in every currency -- a hover listing
 * "$0.01 - EUR0.0091 - GBP0.0078" would look like three different numbers.
 */
function decimalsFor(amountUsd: number): number {
  const size = Math.abs(amountUsd);
  if (size === 0) return 2;
  if (size < 0.001) return 6;
  if (size < 0.01) return 4;
  return 2;
}

/**
 * A cost in the given currency, converted from the stored USD figure.
 *
 * Falls back to the base currency when no rate is known for the target, rather
 * than converting at a guessed one -- an instance with no outbound network
 * shows real dollars instead of invented pounds.
 */
export function formatMoney(
  amountUsd: number,
  currency: Currency = BASE_CURRENCY,
  rates: Rates = {}
): string {
  const rate = currency === BASE_CURRENCY ? 1 : rates[currency];
  const target = rate === undefined ? BASE_CURRENCY : currency;
  const amount = amountUsd * (rate ?? 1);
  const decimals = decimalsFor(amountUsd);

  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: target,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount);
}

/**
 * `formatMoney` with the currency and rates already chosen.
 *
 * Several call sites pass the formatter by reference -- `UsageCell` takes a
 * `format: (value: number) => string`, and the grid columns hand one to each
 * numeric column -- so the currency is bound here rather than threaded through
 * every one of them as an extra argument.
 */
export function makeMoneyFormatter(
  currency: Currency = BASE_CURRENCY,
  rates: Rates = {}
): (amountUsd: number) => string {
  return amountUsd => formatMoney(amountUsd, currency, rates);
}

/**
 * The same cost in every other currency, for a hover.
 *
 * Skips the one already on screen, and any the instance has no rate for.
 */
export function otherCurrencies(
  amountUsd: number,
  currency: Currency,
  rates: Rates
): string[] {
  return CURRENCIES.filter(
    other =>
      other !== currency &&
      (other === BASE_CURRENCY || rates[other] !== undefined)
  ).map(other => formatMoney(amountUsd, other, rates));
}

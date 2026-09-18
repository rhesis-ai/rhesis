import {
  BASE_CURRENCY,
  CURRENCIES,
  formatMoney,
  isAvailable,
  isCurrency,
  makeMoneyFormatter,
  otherCurrencies,
} from '../money';

const RATES = { EUR: 0.871, GBP: 0.74758, CHF: 0.82449 };

describe('formatMoney', () => {
  it('leaves a stored cost alone in the currency it is stored in', () => {
    expect(formatMoney(0.0325, 'USD', RATES)).toBe('$0.03');
  });

  it('converts at the given rate, with the currency named', () => {
    expect(formatMoney(0.0325, 'EUR', RATES)).toBe('€0.03');
    expect(formatMoney(0.0325, 'GBP', RATES)).toBe('£0.02');
    // Intl separates a currency code from the figure with a non-breaking
    // space, which is what keeps them on one line.
    expect(formatMoney(0.0325, 'CHF', RATES)).toBe('CHF\u00a00.03');
  });

  it('defaults to the stored currency when asked for nothing', () => {
    expect(formatMoney(1.5)).toBe('$1.50');
  });

  describe('precision', () => {
    // A cost of a thousandth of a cent still has to say something but zero.
    it('spends more decimals as the figure shrinks', () => {
      expect(formatMoney(10.25)).toBe('$10.25');
      expect(formatMoney(0.005)).toBe('$0.0050');
      expect(formatMoney(0.0001)).toBe('$0.000100');
      expect(formatMoney(0)).toBe('$0.00');
    });

    it('writes one cost to the same precision in every currency', () => {
      // Taken from the stored figure, not the converted one. $0.0105 is just
      // over a cent and takes two decimals; converted it falls under one and
      // would take four, printing the same cost two different ways in one
      // hover.
      expect(formatMoney(0.0105, 'USD', RATES)).toBe('$0.01');
      expect(formatMoney(0.0105, 'GBP', RATES)).toBe('£0.01');
      expect(formatMoney(0.0105, 'EUR', RATES)).toBe('€0.01');
    });

    it('groups the thousands on a cost large enough to need it', () => {
      expect(formatMoney(1234.5)).toBe('$1,234.50');
    });
  });

  describe('when a rate is missing', () => {
    it('shows the stored currency rather than converting at a guess', () => {
      // An instance with no outbound network shows real dollars, not invented
      // pounds.
      expect(formatMoney(1.5, 'GBP', { EUR: 0.871 })).toBe('$1.50');
    });

    it('still handles the stored currency, which needs no rate', () => {
      expect(formatMoney(1.5, 'USD', {})).toBe('$1.50');
    });
  });
});

describe('makeMoneyFormatter', () => {
  it('binds the currency so it can be passed by reference', () => {
    // UsageCell and the grid columns take a format function, not a currency.
    const format = makeMoneyFormatter('EUR', RATES);

    expect([0.0325, 1.5].map(format)).toEqual(['€0.03', '€1.31']);
  });

  it('falls back to the stored currency with no arguments', () => {
    expect(makeMoneyFormatter()(1.5)).toBe('$1.50');
  });
});

describe('otherCurrencies', () => {
  it('lists the same cost everywhere else, for a hover', () => {
    expect(otherCurrencies(0.0325, 'USD', RATES)).toEqual([
      '€0.03',
      '£0.02',
      'CHF\u00a00.03',
    ]);
  });

  it('leaves out the one already on screen', () => {
    expect(otherCurrencies(0.0325, 'EUR', RATES)).not.toContain('€0.03');
  });

  it('leaves out any the instance has no rate for', () => {
    expect(otherCurrencies(1.5, 'USD', { EUR: 0.871 })).toEqual(['€1.31']);
  });

  it('always keeps the stored currency, which needs no rate', () => {
    expect(otherCurrencies(1.5, 'EUR', {})).toContain('$1.50');
  });
});

describe('isCurrency', () => {
  it('accepts the currencies the product offers', () => {
    expect(CURRENCIES.every(isCurrency)).toBe(true);
  });

  it('rejects anything else, including a stored setting gone stale', () => {
    ['JPY', 'usd', '', null, undefined, 42].forEach(value =>
      expect(isCurrency(value)).toBe(false)
    );
  });

  it('agrees with the declared base', () => {
    expect(isCurrency(BASE_CURRENCY)).toBe(true);
  });
});

describe('isAvailable', () => {
  it('needs no rate for the currency costs are stored in', () => {
    expect(isAvailable('USD', {})).toBe(true);
  });

  it('needs a rate for anything else', () => {
    // Without this a picker offers GBP and then renders dollars under it,
    // which is what an instance that could not reach the rate provider did.
    expect(isAvailable('GBP', {})).toBe(false);
    expect(isAvailable('CHF', { EUR: 0.871 })).toBe(false);
  });

  it('is satisfied by a rate being present', () => {
    expect(isAvailable('GBP', RATES)).toBe(true);
  });
});

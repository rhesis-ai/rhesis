import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CurrencyProvider, useCurrency } from '../CurrencyContext';

const getExchangeRates = jest.fn();
const useUserSettings = jest.fn();
const useOrganization = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getServicesClient: () => ({ getExchangeRates }),
  })),
}));

jest.mock('@/hooks/useIsAuthenticated', () => ({
  useIsAuthenticated: () => true,
  useUserScope: () => 'user-1',
}));

jest.mock('@/hooks/useUserSettings', () => ({
  useUserSettings: (...args: unknown[]) => useUserSettings(...args),
}));

jest.mock('@/contexts/OrganizationContext', () => ({
  useOrganization: () => useOrganization(),
}));

const RATES = {
  base: 'USD',
  rates: { EUR: 0.871, GBP: 0.74758, CHF: 0.82449 },
  as_of: '2026-09-17',
};

function setup({
  userCurrency = null,
  orgCurrency = null,
}: { userCurrency?: string | null; orgCurrency?: string | null } = {}) {
  useUserSettings.mockReturnValue({
    data: userCurrency ? { localization: { currency: userCurrency } } : {},
  });
  useOrganization.mockReturnValue({
    organization: orgCurrency
      ? { organization_settings: { display: { currency: orgCurrency } } }
      : { organization_settings: {} },
  });

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <CurrencyProvider>{children}</CurrencyProvider>
    </QueryClientProvider>
  );
  return renderHook(() => useCurrency(), { wrapper });
}

describe('CurrencyProvider', () => {
  beforeEach(() => {
    getExchangeRates.mockReset();
    getExchangeRates.mockResolvedValue(RATES);
  });

  describe('precedence', () => {
    it('uses the currency this person chose', async () => {
      const { result } = setup({ userCurrency: 'CHF', orgCurrency: 'EUR' });

      await waitFor(() => expect(result.current.currency).toBe('CHF'));
    });

    it("falls back to the organization's when the person chose none", async () => {
      const { result } = setup({ orgCurrency: 'EUR' });

      await waitFor(() => expect(result.current.currency).toBe('EUR'));
    });

    it('falls back to the stored currency when neither chose one', async () => {
      const { result } = setup();

      await waitFor(() => expect(result.current.currency).toBe('USD'));
    });

    it('reports both choices, so a picker can name the default', async () => {
      const { result } = setup({ userCurrency: 'GBP', orgCurrency: 'EUR' });

      await waitFor(() => expect(result.current.userCurrency).toBe('GBP'));
      expect(result.current.organizationCurrency).toBe('EUR');
    });
  });

  describe('a stored value the product no longer offers', () => {
    it('is ignored rather than handed to Intl', async () => {
      // A currency dropped from the constant would otherwise throw inside
      // Intl.NumberFormat and take the page with it.
      const { result } = setup({ userCurrency: 'JPY', orgCurrency: 'EUR' });

      await waitFor(() => expect(result.current.currency).toBe('EUR'));
    });
  });

  describe('formatting', () => {
    it('converts at the fetched rate', async () => {
      const { result } = setup({ userCurrency: 'EUR' });

      await waitFor(() => expect(result.current.format(1)).toBe('€0.87'));
    });

    it('lists the same cost in the other currencies for a hover', async () => {
      const { result } = setup({ userCurrency: 'EUR' });

      await waitFor(() =>
        expect(result.current.alternatives(1)).toEqual([
          '$1.00',
          '£0.75',
          'CHF 0.82',
        ])
      );
    });

    it('offers a hover naming the other currencies and the rates date', async () => {
      const { result } = setup({ userCurrency: 'EUR' });

      await waitFor(() =>
        expect(result.current.alternativesTitle(1)).toBe(
          '$1.00 \u00b7 £0.75 \u00b7 CHF\u00a00.82\nRates of 2026-09-17'
        )
      );
    });

    it('says the rate age is unknown when the rates came from a fallback', async () => {
      getExchangeRates.mockResolvedValue({ ...RATES, as_of: null });
      const { result } = setup({ userCurrency: 'EUR' });

      await waitFor(() =>
        expect(result.current.alternativesTitle(1)).toContain(
          'Rate age unknown'
        )
      );
    });

    it('offers no hover when there is nothing to compare against', async () => {
      // No rates fetched, so USD is the only currency available and it is
      // already the one on screen.
      getExchangeRates.mockRejectedValue(new Error('offline'));
      const { result } = setup();

      await waitFor(() => expect(getExchangeRates).toHaveBeenCalled());
      expect(result.current.alternativesTitle(1)).toBeUndefined();
    });

    it('carries the day the rates are from', async () => {
      const { result } = setup();

      await waitFor(() => expect(result.current.asOf).toBe('2026-09-17'));
    });
  });

  describe('when the rates cannot be fetched', () => {
    it('shows costs as stored rather than converting at a guess', async () => {
      getExchangeRates.mockRejectedValue(new Error('offline'));
      const { result } = setup({ userCurrency: 'EUR' });

      await waitFor(() => expect(getExchangeRates).toHaveBeenCalled());
      // The preference is honoured where possible, but with no rate there is
      // nothing to convert by, so the figure stays in the currency it is in.
      expect(result.current.format(1)).toBe('$1.00');
      expect(result.current.asOf).toBeNull();
    });
  });
});

describe('useCurrency outside a provider', () => {
  it('formats costs as stored rather than throwing', () => {
    const { result } = renderHook(() => useCurrency());

    expect(result.current.currency).toBe('USD');
    expect(result.current.format(1.5)).toBe('$1.50');
  });
});

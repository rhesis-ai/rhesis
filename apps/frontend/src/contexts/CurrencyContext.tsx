'use client';

import React, { createContext, useContext, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { useUserSettings } from '@/hooks/useUserSettings';
import { useOrganization } from '@/contexts/OrganizationContext';
import { exchangeRateKeys } from '@/constants/query-keys';
import {
  BASE_CURRENCY,
  isCurrency,
  makeMoneyFormatter,
  otherCurrencies,
  type Currency,
  type Rates,
} from '@/utils/money';

interface CurrencyContextValue {
  /** The currency costs are shown in, after the precedence below. */
  currency: Currency;
  rates: Rates;
  /** The business day the rates are from, or null when that is unknown. */
  asOf: string | null;
  /** Bound formatter, for the call sites that pass one by reference. */
  format: (amountUsd: number) => string;
  /** The same cost in every other currency, for a hover. */
  alternatives: (amountUsd: number) => string[];
  /** Those alternatives as a native title, with the rates' date. */
  alternativesTitle: (amountUsd: number) => string | undefined;
  /** What the organization chose, so a picker can name the default. */
  organizationCurrency: Currency | null;
  /** What this user chose, if anything. Null means they follow the org. */
  userCurrency: Currency | null;
}

const FALLBACK: CurrencyContextValue = {
  currency: BASE_CURRENCY,
  rates: {},
  asOf: null,
  format: makeMoneyFormatter(),
  alternatives: () => [],
  alternativesTitle: () => undefined,
  organizationCurrency: null,
  userCurrency: null,
};

const CurrencyContext = createContext<CurrencyContextValue>(FALLBACK);

/** A day, matching the server's own cache; the rates change once a day. */
const RATES_STALE_MS = 24 * 60 * 60 * 1000;

function asCurrency(value: unknown): Currency | null {
  return isCurrency(value) ? value : null;
}

/**
 * The currency costs are shown in, and the rates to get there.
 *
 * Resolved as **user setting, then organization setting, then USD**. The
 * organization decides how its spend is read by default; someone in another
 * country can override it for themselves without changing what anyone else
 * sees. An unrecognised stored value -- a currency the product no longer
 * offers -- is ignored rather than passed to Intl.
 *
 * Costs are stored in USD, so USD always works. If the rates cannot be
 * fetched, everything falls back to showing them as stored rather than
 * converting at a rate nobody has.
 */
export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useIsAuthenticated();
  const { data: userSettings } = useUserSettings(isAuthenticated);
  const { organization } = useOrganization();

  const { data: rateData } = useQuery({
    queryKey: exchangeRateKeys.all(),
    queryFn: () =>
      new ApiClientFactory().getServicesClient().getExchangeRates(),
    enabled: isAuthenticated,
    staleTime: RATES_STALE_MS,
    // Showing costs as stored is a fine outcome; retrying is not worth it.
    retry: false,
  });

  const value = useMemo<CurrencyContextValue>(() => {
    const userCurrency = asCurrency(userSettings?.localization?.currency);
    const organizationCurrency = asCurrency(
      organization?.organization_settings?.display?.currency
    );
    const currency = userCurrency ?? organizationCurrency ?? BASE_CURRENCY;
    const rates = rateData?.rates ?? {};

    return {
      currency,
      rates,
      asOf: rateData?.as_of ?? null,
      format: makeMoneyFormatter(currency, rates),
      alternatives: (amountUsd: number) =>
        otherCurrencies(amountUsd, currency, rates),
      alternativesTitle: (amountUsd: number) => {
        const others = otherCurrencies(amountUsd, currency, rates);
        if (others.length === 0) return undefined;
        const dated = rateData?.as_of
          ? `Rates of ${rateData.as_of}`
          : 'Rate age unknown';
        return `${others.join(' \u00b7 ')}\n${dated}`;
      },
      organizationCurrency,
      userCurrency,
    };
  }, [
    userSettings?.localization?.currency,
    organization?.organization_settings?.display?.currency,
    rateData,
  ]);

  return (
    <CurrencyContext.Provider value={value}>
      {children}
    </CurrencyContext.Provider>
  );
}

/**
 * The active currency and a formatter bound to it.
 *
 * Outside a provider this reports USD and formats costs as stored, so a
 * component rendered in isolation — a test, a storybook — still shows a real
 * figure rather than throwing.
 */
export function useCurrency(): CurrencyContextValue {
  return useContext(CurrencyContext);
}

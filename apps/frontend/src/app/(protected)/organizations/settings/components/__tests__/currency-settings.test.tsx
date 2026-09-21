/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import OrganizationCurrencyForm from '../OrganizationCurrencyForm';
import PreferencesForm from '../../../../settings/components/PreferencesForm';
import type { Organization } from '@/utils/api-client/interfaces/organization';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getOrganizationsClient: () => ({
      updateOrganizationSettings: jest.fn().mockResolvedValue({}),
    }),
    getUsersClient: () => ({
      updateUserSettings: jest.fn().mockResolvedValue({}),
    }),
  })),
}));

jest.mock('@/contexts/CurrencyContext', () => ({
  useCurrency: () => ({
    currency: 'EUR',
    rates: { EUR: 0.92, GBP: 0.79, CHF: 0.88 },
    organizationCurrency: 'EUR',
    userCurrency: null,
    format: (value: number) => `$${value.toFixed(2)}`,
  }),
}));

jest.mock('@/hooks/useIsAuthenticated', () => ({
  useUserScope: () => 'user-1',
}));

jest.mock('@/hooks/useUserSettings', () => ({
  writeUserSettingsCache: jest.fn(),
}));

function organization(): Organization {
  return {
    id: 'org-1',
    name: 'Acme',
    createdAt: '2026-01-01',
    owner_id: 'u1' as any,
    user_id: 'u1' as any,
    organization_settings: { version: 1 } as any,
  };
}

function renderOrganizationForm() {
  return render(
    <OrganizationCurrencyForm
      organization={organization()}
      onUpdate={jest.fn()}
    />
  );
}

function renderPersonalForm() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <PreferencesForm />
    </QueryClientProvider>
  );
}

/** The paragraph under the select, which must be word for word the same in both. */
const SHARED_EXPLANATION =
  'Costs are recorded in USD and converted at the daily European Central Bank ' +
  'reference rate. This changes how costs are shown, not what was spent.';

/**
 * Lives beside the organization form but covers both, because the whole point is
 * that the two say the same thing. Split across two files they drift again.
 */
describe('currency settings', () => {
  it('names the section and the select the same way in both places', () => {
    const org = renderOrganizationForm();
    const personal = renderPersonalForm();

    for (const view of [org, personal]) {
      const scope = within(view.container);
      expect(scope.getByRole('heading', { name: 'Currency' })).toBeVisible();
      // The organization select used to be labelled "Organization currency",
      // which named the owner rather than the setting.
      expect(scope.getByLabelText('Currency')).toBeInTheDocument();
    }
  });

  it('explains the conversion in the same words in both places', () => {
    // Two copies of one explanation is how they drifted the first time: the
    // organization said "how they are displayed", the personal one said
    // "what you see", about the same rate and the same figures.
    const org = renderOrganizationForm();
    const personal = renderPersonalForm();

    for (const view of [org, personal]) {
      expect(view.container.textContent).toContain(SHARED_EXPLANATION);
    }
  });

  it('says the organization setting is the default others can override', () => {
    renderOrganizationForm();

    expect(
      screen.getByText(/default for everyone in the organization/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/override it in their own preferences/)
    ).toBeInTheDocument();
  });

  it('says the personal setting applies to one person and wins', () => {
    renderPersonalForm();

    expect(screen.getByText(/applies to you only/)).toBeInTheDocument();
    expect(
      screen.getByText(/overrides the organization's default/)
    ).toBeInTheDocument();
  });

  it('offers only the personal form a way back to the organization default', () => {
    renderPersonalForm();
    fireEvent.mouseDown(screen.getByRole('combobox'));

    expect(
      screen.getByRole('option', { name: /Use the organization's currency/ })
    ).toBeInTheDocument();
  });

  it('gives the organization form no option to defer to anything', () => {
    renderOrganizationForm();
    fireEvent.mouseDown(screen.getByRole('combobox'));

    expect(
      screen.queryByRole('option', { name: /Use the organization's/ })
    ).not.toBeInTheDocument();
  });
});

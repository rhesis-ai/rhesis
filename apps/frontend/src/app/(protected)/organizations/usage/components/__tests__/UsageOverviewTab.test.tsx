import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';

import UsageOverviewTab from '../UsageOverviewTab';
import { useUsage } from '@/contexts/UsageContext';

jest.mock('@/contexts/UsageContext', () => ({
  useUsage: jest.fn(),
}));

const mockUseUsage = useUsage as jest.Mock;

const USAGE_RESOURCES = {
  test_executions: {
    used: 5,
    limit: 1000,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind: 'flow' as const,
  },
  model_tokens: {
    used: 999,
    limit: null,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind: 'flow' as const,
  },
  seats: {
    used: 3,
    limit: 10,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind: 'stock' as const,
  },
};

beforeEach(() => {
  mockUseUsage.mockReset();
  mockUseUsage.mockReturnValue({
    resources: USAGE_RESOURCES,
    edition: 'community',
    loading: false,
    error: null,
  });
});

describe('UsageOverviewTab', () => {
  it('shows a loading skeleton while usage is loading', () => {
    mockUseUsage.mockReturnValue({
      resources: {},
      edition: null,
      loading: true,
      error: null,
    });

    render(<UsageOverviewTab />);

    expect(screen.queryByText('Metered Resources')).not.toBeInTheDocument();
  });

  it('shows an error message when usage fails to load', () => {
    mockUseUsage.mockReturnValue({
      resources: {},
      edition: null,
      loading: false,
      error: new Error('boom'),
    });

    render(<UsageOverviewTab />);

    expect(
      screen.getByText('Could not load usage data. Please try again later.')
    ).toBeInTheDocument();
  });

  it('groups resources into Metered Resources (flow) and Resource Counts (stock)', () => {
    render(<UsageOverviewTab />);

    expect(screen.getByText('Metered Resources')).toBeInTheDocument();
    expect(screen.getByText('Resource Counts')).toBeInTheDocument();
    expect(screen.getByText('Test Executions')).toBeInTheDocument();
    expect(screen.getByText('Seats')).toBeInTheDocument();
  });

  it('shows the billing period and edition in the subtitle', () => {
    render(<UsageOverviewTab />);

    expect(
      screen.getByText(/Current billing period:.*community plan/)
    ).toBeInTheDocument();
  });

  it('renders "Unlimited" for a resource with no limit', () => {
    render(<UsageOverviewTab />);

    expect(screen.getByText(/999.*\(Unlimited\)/)).toBeInTheDocument();
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import UsageOverviewTab from '../UsageOverviewTab';
import { useUsageForPeriod } from '@/hooks/useUsageForPeriod';

jest.mock('@/hooks/useUsageForPeriod', () => ({
  useUsageForPeriod: jest.fn(),
}));

const mockUseUsage = useUsageForPeriod as jest.Mock;

const USAGE_RESOURCES = {
  test_executions: {
    used: 5,
    limit: 1000,
    ceiling: 1000,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind: 'flow' as const,
  },
  model_tokens: {
    used: 999,
    limit: null,
    ceiling: null,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind: 'flow' as const,
  },
  seats: {
    used: 3,
    limit: 10,
    ceiling: 10,
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

    expect(screen.queryByText('Test Runs')).not.toBeInTheDocument();
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

  it('renders every resource as a flat list, with no category headers', () => {
    render(<UsageOverviewTab />);

    expect(screen.getByText('Test Runs')).toBeInTheDocument();
    expect(screen.getByText('Seats')).toBeInTheDocument();
    expect(screen.queryByText('Metered Resources')).not.toBeInTheDocument();
    expect(screen.queryByText('Resource Counts')).not.toBeInTheDocument();
  });

  it('shows the usage period in the subtitle', () => {
    render(<UsageOverviewTab />);

    expect(screen.getByText(/Current usage period:/)).toBeInTheDocument();
  });

  it('renders "Unlimited" for a resource with no limit', () => {
    render(<UsageOverviewTab />);

    expect(screen.getByText(/999.*\(Unlimited\)/)).toBeInTheDocument();
  });

  it('shows a plan chip and an upgrade link for the community edition', () => {
    render(<UsageOverviewTab />);

    expect(screen.getByText('Community plan')).toBeInTheDocument();
    const upgradeLink = screen.getByRole('link', { name: 'Upgrade' });
    expect(upgradeLink).toHaveAttribute('href', 'https://rhesis.ai/editions');
    expect(upgradeLink).toHaveAttribute('target', '_blank');
    expect(upgradeLink).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('does not mark stock resources as live counts for the current period', () => {
    render(<UsageOverviewTab />);

    expect(screen.queryByText('as of today')).not.toBeInTheDocument();
  });

  it('marks stock resources as live counts once a past period is selected', () => {
    render(<UsageOverviewTab />);

    fireEvent.click(screen.getByRole('button', { name: 'Filters' }));
    fireEvent.mouseDown(screen.getByLabelText('Period'));
    fireEvent.click(screen.getAllByRole('option')[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    // One hint, on Seats (the only stock resource in the fixture) -- not on
    // the flow resources, which do reflect the selected period.
    expect(screen.getByText('as of today')).toBeInTheDocument();
  });

  it('counts the period filter on the badge once a past period is selected', () => {
    render(<UsageOverviewTab />);

    expect(screen.queryByLabelText(/active filters/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Filters' }));
    fireEvent.mouseDown(screen.getByLabelText('Period'));
    fireEvent.click(screen.getAllByRole('option')[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    // The count, not just a bare dot: FilterButton renders an empty circle
    // when handed only hasActiveFilters.
    expect(screen.getByLabelText('1 active filters')).toHaveTextContent('1');
  });

  it('labels the period from a flow resource, not whichever comes first', () => {
    // Stock items carry the *current* period while flow items carry the
    // requested one, so a stock-first response must not retitle the card.
    mockUseUsage.mockReturnValue({
      resources: {
        seats: {
          used: 3,
          limit: 10,
          ceiling: 10,
          period_start: '2026-08-01',
          period_end: '2026-08-31',
          kind: 'stock' as const,
        },
        test_executions: {
          used: 5,
          limit: 1000,
          ceiling: 1000,
          period_start: '2026-01-01',
          period_end: '2026-01-31',
          kind: 'flow' as const,
        },
      },
      edition: 'community',
      loading: false,
      error: null,
    });

    render(<UsageOverviewTab />);

    expect(screen.getByText(/Jan 1, 2026 – Jan 31, 2026/)).toBeInTheDocument();
  });

  it('hides the upgrade link for a paid edition', () => {
    mockUseUsage.mockReturnValue({
      resources: USAGE_RESOURCES,
      edition: 'enterprise',
      loading: false,
      error: null,
    });

    render(<UsageOverviewTab />);

    expect(screen.getByText('Enterprise plan')).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Upgrade' })
    ).not.toBeInTheDocument();
  });
});

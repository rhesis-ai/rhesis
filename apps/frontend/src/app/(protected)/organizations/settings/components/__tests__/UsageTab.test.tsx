import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import UsageTab from '../UsageTab';
import { useUsage } from '@/contexts/UsageContext';
import { useUsageHistory } from '@/hooks/useUsageHistory';

jest.mock('@/contexts/UsageContext', () => ({
  useUsage: jest.fn(),
}));

jest.mock('@/hooks/useUsageHistory', () => ({
  useUsageHistory: jest.fn(),
}));

const mockUseUsage = useUsage as jest.Mock;
const mockUseUsageHistory = useUsageHistory as jest.Mock;

const USAGE_RESOURCES = {
  test_executions: {
    used: 5,
    limit: 1000,
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

function historyState(
  overrides: Partial<ReturnType<typeof useUsageHistory>> = {}
) {
  return {
    // Deliberately a resource absent from USAGE_RESOURCES above (which only
    // has test_executions/seats): the chart title and a meter label
    // rendering the same text would make getByText ambiguous.
    resources: {
      tracing_spans: [
        { period_start: '2026-06-01', used: 1 },
        { period_start: '2026-07-01', used: 2 },
        { period_start: '2026-08-01', used: 5 },
      ],
    },
    loading: false,
    error: null,
    ...overrides,
  };
}

beforeEach(() => {
  mockUseUsage.mockReset();
  mockUseUsageHistory.mockReset();
  mockUseUsage.mockReturnValue({
    resources: USAGE_RESOURCES,
    edition: 'community',
    loading: false,
    error: null,
  });
  mockUseUsageHistory.mockReturnValue(historyState());
});

describe('UsageTab history section', () => {
  it('renders a chart title per flow resource returned by the history hook', () => {
    render(<UsageTab />);

    expect(screen.getByText('Usage Over Time')).toBeInTheDocument();
    // Chart title -- one per key in useUsageHistory's resources map.
    expect(screen.getByText('Tracing Spans')).toBeInTheDocument();
  });

  it('defaults to the 6-month filter and requests history for it', () => {
    render(<UsageTab />);

    expect(mockUseUsageHistory).toHaveBeenCalledWith(6);
  });

  it('switches the requested range when a different pill is clicked', () => {
    render(<UsageTab />);

    fireEvent.click(screen.getByText('12M'));

    expect(mockUseUsageHistory).toHaveBeenLastCalledWith(12);
  });

  it('shows a loading state instead of charts while history is loading', () => {
    mockUseUsageHistory.mockReturnValue(
      historyState({ loading: true, resources: {} })
    );

    render(<UsageTab />);

    expect(screen.queryByText('Tracing Spans')).not.toBeInTheDocument();
  });

  it('shows an error message when history fails to load', () => {
    mockUseUsageHistory.mockReturnValue(
      historyState({ error: new Error('boom'), resources: {} })
    );

    render(<UsageTab />);

    expect(
      screen.getByText('Could not load usage history. Please try again later.')
    ).toBeInTheDocument();
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import UsageOverTimeTab from '../UsageOverTimeTab';
import { useUsageHistory } from '@/hooks/useUsageHistory';

jest.mock('@/hooks/useUsageHistory', () => ({
  useUsageHistory: jest.fn(),
}));

const mockUseUsageHistory = useUsageHistory as jest.Mock;

function historyState(
  overrides: Partial<ReturnType<typeof useUsageHistory>> = {}
) {
  return {
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
  mockUseUsageHistory.mockReset();
  mockUseUsageHistory.mockReturnValue(historyState());
});

describe('UsageOverTimeTab', () => {
  it('renders a chart title per flow resource returned by the history hook', () => {
    render(<UsageOverTimeTab />);

    expect(screen.getByText('Usage Over Time')).toBeInTheDocument();
    expect(screen.getByText('Tracing Spans')).toBeInTheDocument();
  });

  it('defaults to the 6-month filter and requests history for it', () => {
    render(<UsageOverTimeTab />);

    expect(mockUseUsageHistory).toHaveBeenCalledWith(6);
    expect(screen.getByText('Showing the last 6 months')).toBeInTheDocument();
  });

  it('switches the requested range when a different pill is clicked', () => {
    render(<UsageOverTimeTab />);

    fireEvent.click(screen.getByText('12M'));

    expect(mockUseUsageHistory).toHaveBeenLastCalledWith(12);
    expect(screen.getByText('Showing the last 12 months')).toBeInTheDocument();
  });

  it('shows a loading state instead of charts while history is loading', () => {
    mockUseUsageHistory.mockReturnValue(
      historyState({ loading: true, resources: {} })
    );

    render(<UsageOverTimeTab />);

    expect(screen.queryByText('Tracing Spans')).not.toBeInTheDocument();
  });

  it('shows an error message when history fails to load', () => {
    mockUseUsageHistory.mockReturnValue(
      historyState({ error: new Error('boom'), resources: {} })
    );

    render(<UsageOverTimeTab />);

    expect(
      screen.getByText('Could not load usage history. Please try again later.')
    ).toBeInTheDocument();
  });

  it('shows a no-history message instead of a flat zero-line chart', () => {
    mockUseUsageHistory.mockReturnValue(
      historyState({
        resources: {
          tracing_spans: [
            { period_start: '2026-06-01', used: 0 },
            { period_start: '2026-07-01', used: 0 },
            { period_start: '2026-08-01', used: 0 },
          ],
        },
      })
    );

    render(<UsageOverTimeTab />);

    expect(screen.getByText('Tracing Spans')).toBeInTheDocument();
    expect(screen.getByText('No history for this period')).toBeInTheDocument();
    expect(
      document.querySelector('.MuiChartsSurface-root')
    ).not.toBeInTheDocument();
  });

  it('renders the chart (not the no-history message) when at least one point is non-zero', () => {
    mockUseUsageHistory.mockReturnValue(
      historyState({
        resources: {
          tracing_spans: [
            { period_start: '2026-06-01', used: 0 },
            { period_start: '2026-07-01', used: 0 },
            { period_start: '2026-08-01', used: 1 },
          ],
        },
      })
    );

    render(<UsageOverTimeTab />);

    expect(
      screen.queryByText('No history for this period')
    ).not.toBeInTheDocument();
    expect(
      document.querySelector('.MuiChartsSurface-root')
    ).toBeInTheDocument();
  });
});

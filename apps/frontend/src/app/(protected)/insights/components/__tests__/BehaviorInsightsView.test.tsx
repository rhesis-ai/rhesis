import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import BehaviorInsightsView from '../BehaviorInsightsView';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';

jest.mock('../BehaviorInsightsRow', () => {
  return function MockBehaviorInsightsRow({
    row,
  }: {
    row: Array<{ name: string }>;
  }) {
    return (
      <div data-testid="behavior-insights-row">
        {row.map(column => column.name).join(',')}
      </div>
    );
  };
});

jest.mock('../BehaviorColumn', () => {
  return function MockBehaviorColumn() {
    return <div data-testid="behavior-column-skeleton" />;
  };
});

const defaultColumn = {
  id: 'beh-1',
  name: 'Safety',
  overall: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
  metrics: [],
  topics: [],
};

function renderView(
  props: Partial<React.ComponentProps<typeof BehaviorInsightsView>> = {}
) {
  const defaults: React.ComponentProps<typeof BehaviorInsightsView> = {
    sessionToken: 'token',
    filters: { ...DEFAULT_INSIGHTS_FILTERS, endpointId: 'ep-1' },
    insights: {
      summary: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
      columns: [defaultColumn],
      failedTestCaseCount: 2,
      loading: false,
      error: null,
      noRuns: false,
    },
    columnRows: [[defaultColumn]],
    expandedRows: new Set([0]),
    onRowToggle: jest.fn(),
  };

  return render(<BehaviorInsightsView {...defaults} {...props} />);
}

describe('BehaviorInsightsView', () => {
  it('renders summary bar and behavior rows when runs exist', () => {
    renderView();

    expect(screen.getByText(/80\.0%/)).toBeInTheDocument();
    expect(screen.getByTestId('behavior-insights-row')).toHaveTextContent(
      'Safety'
    );
  });

  it('shows loading skeleton while insights are loading', () => {
    renderView({
      insights: {
        summary: null,
        columns: [],
        failedTestCaseCount: 0,
        loading: true,
        error: null,
        noRuns: false,
      },
      columnRows: [],
    });

    expect(screen.getByText('Loading results…')).toBeInTheDocument();
    expect(screen.getAllByTestId('behavior-column-skeleton')).toHaveLength(6);
  });
});

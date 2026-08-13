import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import RequirementInsightsView from '../RequirementInsightsView';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';

jest.mock('../RequirementInsightsRow', () => {
  return function MockRequirementInsightsRow({
    row,
  }: {
    row: Array<{ name: string }>;
  }) {
    return (
      <div data-testid="requirement-insights-row">
        {row.map(column => column.name).join(',')}
      </div>
    );
  };
});

jest.mock('../RequirementColumn', () => {
  return function MockRequirementColumn() {
    return <div data-testid="requirement-column-skeleton" />;
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
  props: Partial<React.ComponentProps<typeof RequirementInsightsView>> = {}
) {
  const defaults: React.ComponentProps<typeof RequirementInsightsView> = {
    filters: { ...DEFAULT_INSIGHTS_FILTERS, endpointId: 'ep-1' },
    insights: {
      summary: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
      columns: [defaultColumn],
      loading: false,
      error: null,
      noRuns: false,
    },
    columnRows: [[defaultColumn]],
    expandedRows: new Set([0]),
    onRowToggle: jest.fn(),
  };

  return render(<RequirementInsightsView {...defaults} {...props} />);
}

describe('RequirementInsightsView', () => {
  it('renders summary bar and requirement rows when runs exist', () => {
    renderView();

    expect(screen.getByText(/80\.0%/)).toBeInTheDocument();
    expect(screen.getByTestId('requirement-insights-row')).toHaveTextContent(
      'Safety'
    );
  });

  it('shows loading skeleton while insights are loading', () => {
    renderView({
      insights: {
        summary: null,
        columns: [],
        loading: true,
        error: null,
        noRuns: false,
      },
      columnRows: [],
    });

    expect(screen.getByText('Loading results…')).toBeInTheDocument();
    expect(screen.getAllByTestId('requirement-column-skeleton')).toHaveLength(6);
  });
});

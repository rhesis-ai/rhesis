import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import BehaviorInsightsView from '../BehaviorInsightsView';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';

const mockPush = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
}));

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

afterEach(() => {
  jest.clearAllMocks();
});

describe('BehaviorInsightsView', () => {
  it('renders no-endpoints empty state with navigation CTA', async () => {
    const user = userEvent.setup();
    renderView({ noEndpoints: true });

    expect(
      screen.getByRole('heading', { name: 'No endpoints in this project' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Create an endpoint to view behavior insights for your AI application.'
      )
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Go to Endpoints' }));
    expect(mockPush).toHaveBeenCalledWith('/endpoints');
  });

  it('renders no-test-results empty state without summary bar or info alert', async () => {
    const user = userEvent.setup();
    renderView({
      insights: {
        summary: { total: 0, passed: 0, failed: 0, pass_rate: 0 },
        columns: [],
        loading: false,
        error: null,
        noRuns: true,
      },
      columnRows: [],
    });

    expect(
      screen.getByRole('heading', { name: 'No test results yet' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Run a test set against your endpoint to generate your first test run and view behavior insights.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/pass rate/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/no test runs found for this endpoint/i)
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Go to Test Sets' }));
    expect(mockPush).toHaveBeenCalledWith('/test-sets');
  });

  it('does not show empty state while loading test results', () => {
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

    expect(
      screen.queryByRole('heading', { name: 'No test results yet' })
    ).not.toBeInTheDocument();
    expect(screen.getByText('Loading results…')).toBeInTheDocument();
    expect(screen.getAllByTestId('behavior-column-skeleton')).toHaveLength(6);
  });

  it('renders summary bar and behavior rows when runs exist', () => {
    renderView();

    expect(screen.getByText(/80\.0%/)).toBeInTheDocument();
    expect(screen.getByTestId('behavior-insights-row')).toHaveTextContent(
      'Safety'
    );
  });
});

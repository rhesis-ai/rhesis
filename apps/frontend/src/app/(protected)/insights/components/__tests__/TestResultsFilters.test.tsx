import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestResultsFilters from '../TestResultsFilters';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';

jest.mock('@/utils/insights-endpoint', () => ({
  writeInsightsEndpointId: jest.fn(),
}));

jest.mock('../InsightsFilterDrawer', () => ({
  __esModule: true,
  default: ({
    open,
    onApply,
  }: {
    open: boolean;
    onApply: (filters: {
      endpointId: string;
      behaviorIds: string[];
      runFilterMode: 'timeRange' | 'testRuns';
      timeRange: '1m' | '7d';
      testRunIds: string[];
    }) => void;
  }) =>
    open ? (
      <div role="presentation">
        <button
          type="button"
          onClick={() =>
            onApply({
              endpointId: 'ep-2',
              behaviorIds: [],
              runFilterMode: 'testRuns',
              timeRange: '1m',
              testRunIds: ['run-1'],
            })
          }
        >
          Apply
        </button>
      </div>
    ) : null,
  countActiveInsightsDrawerFilters: () => 1,
  hasActiveInsightsDrawerFilters: () => true,
}));

import { writeInsightsEndpointId } from '@/utils/insights-endpoint';

function makeEndpoint(id: string, name: string) {
  return {
    id,
    name,
    project_id: 'project-1',
    connection_type: 'REST' as const,
    environment: 'development' as const,
    config_source: 'manual' as const,
    response_format: 'json' as const,
  };
}

const defaultEndpoints = [
  makeEndpoint('ep-1', 'Endpoint One'),
  makeEndpoint('ep-2', 'Endpoint Two'),
];

function renderFilters(
  props: Partial<React.ComponentProps<typeof TestResultsFilters>> = {}
) {
  const defaults = {
    filters: {
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-1',
    },
    onFiltersChange: jest.fn(),
    projectEndpoints: defaultEndpoints,
    endpointsLoading: false,
    behaviorOptions: [
      { id: 'beh-1', name: 'Safety', count: 12 },
      { id: 'beh-2', name: 'Fluency', count: 8 },
    ],
    searchQuery: '',
    onSearchChange: jest.fn(),
  };
  return {
    ...render(<TestResultsFilters {...defaults} {...props} />),
    ...defaults,
    ...props,
  };
}

async function openFilterDrawer(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /filters/i }));
}

afterEach(() => {
  jest.clearAllMocks();
});

describe('TestResultsFilters', () => {
  it('renders search input', () => {
    renderFilters();
    expect(
      screen.getByPlaceholderText(/search behaviors/i)
    ).toBeInTheDocument();
  });

  it('calls onSearchChange when typing in search', async () => {
    const user = userEvent.setup();
    const onSearchChange = jest.fn();
    renderFilters({ onSearchChange });

    await user.type(screen.getByPlaceholderText(/search behaviors/i), 'safe');

    expect(onSearchChange).toHaveBeenCalled();
  });

  it('opens the filter drawer', async () => {
    const user = userEvent.setup();
    renderFilters();
    await openFilterDrawer(user);

    expect(screen.getByRole('presentation')).toBeInTheDocument();
  });

  it('persists endpoint and test run selection when applied from drawer', async () => {
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });
    await openFilterDrawer(user);

    const drawer = screen.getByRole('presentation');
    await user.click(within(drawer).getByRole('button', { name: /apply/i }));

    expect(writeInsightsEndpointId).toHaveBeenCalledWith('ep-2');
    expect(onFiltersChange).toHaveBeenCalledWith({
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-2',
      runFilterMode: 'testRuns',
      testRunIds: ['run-1'],
    });
  });

  it('shows active filter badge when endpoint is selected', () => {
    renderFilters();
    expect(screen.getByLabelText(/1 active filters/i)).toBeInTheDocument();
  });

  it('hides behavior search in compact variant but keeps filters', () => {
    renderFilters({ variant: 'compact' });

    expect(
      screen.queryByPlaceholderText(/search behaviors/i)
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /filters/i })
    ).toBeInTheDocument();
  });
});

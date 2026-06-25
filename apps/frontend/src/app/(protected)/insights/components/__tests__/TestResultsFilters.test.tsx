import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestResultsFilters from '../TestResultsFilters';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';

jest.mock('@/utils/insights-endpoint', () => ({
  writeInsightsEndpointId: jest.fn(),
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
    filters: { timeRange: '1m' as const, endpointId: 'ep-1', behaviorIds: [] },
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
  it('selects 1M by default', () => {
    render(
      <TestResultsFilters
        filters={DEFAULT_INSIGHTS_FILTERS}
        onFiltersChange={jest.fn()}
        projectEndpoints={defaultEndpoints}
        endpointsLoading={false}
        searchQuery=""
        onSearchChange={jest.fn()}
        behaviorOptions={[]}
      />
    );

    expect(screen.getByRole('button', { name: '1M' })).toHaveStyle({
      color: 'rgb(255, 255, 255)',
    });
  });

  it('renders time range pill tabs', () => {
    renderFilters();
    expect(screen.getByRole('button', { name: '1D' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '7D' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '1M' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '3M' })).toBeInTheDocument();
  });

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

  it('renders endpoint dropdown in filter drawer', async () => {
    const user = userEvent.setup();
    renderFilters();
    await openFilterDrawer(user);

    const drawer = screen.getByRole('presentation');
    expect(within(drawer).getByLabelText(/endpoint/i)).toBeInTheDocument();
  });

  it('calls onFiltersChange when a time range pill is clicked', async () => {
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });

    await user.click(screen.getByRole('button', { name: '7D' }));

    expect(onFiltersChange).toHaveBeenCalledWith({
      timeRange: '7d',
      endpointId: 'ep-1',
      behaviorIds: [],
    });
  });

  it('persists endpoint selection to cookie when applied from drawer', async () => {
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });
    await openFilterDrawer(user);

    const drawer = screen.getByRole('presentation');
    await user.click(within(drawer).getByLabelText(/endpoint/i));
    await user.click(screen.getByRole('option', { name: 'Endpoint Two' }));
    await user.click(within(drawer).getByRole('button', { name: /apply/i }));

    expect(writeInsightsEndpointId).toHaveBeenCalledWith('ep-2');
    expect(onFiltersChange).toHaveBeenCalledWith({
      timeRange: '1m',
      endpointId: 'ep-2',
      behaviorIds: [],
    });
  });

  it('shows active filter badge when endpoint is selected', () => {
    renderFilters();
    expect(screen.getByLabelText(/1 active filters/i)).toBeInTheDocument();
  });

  it('disables endpoint dropdown while loading', async () => {
    const user = userEvent.setup();
    renderFilters({ endpointsLoading: true });
    await openFilterDrawer(user);

    const drawer = screen.getByRole('presentation');
    expect(within(drawer).getByLabelText(/endpoint/i)).toHaveAttribute(
      'aria-disabled',
      'true'
    );
  });
});

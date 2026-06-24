import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestResultsFilters from '../TestResultsFilters';

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn(),
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({
    activeProject: { id: 'project-1', name: 'Test Project' },
    projects: [],
    loading: false,
    setActiveProject: jest.fn(),
    refresh: jest.fn(),
  }),
}));

jest.mock('@/utils/insights-endpoint', () => ({
  readInsightsEndpointId: jest.fn(() => null),
  writeInsightsEndpointId: jest.fn(),
  clearInsightsEndpointId: jest.fn(),
}));

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { writeInsightsEndpointId } from '@/utils/insights-endpoint';

function makeEndpoint(id: string, name: string) {
  return {
    id,
    name,
    project_id: 'project-1',
    connection_type: 'REST' as const,
    environment: 'development' as const,
    config_source: 'manual' as const,
  };
}

function mockApiFactory(endpoints: unknown[] = []) {
  const mockGetEndpoints = jest.fn().mockResolvedValue({
    data: endpoints,
    pagination: { totalCount: endpoints.length },
  });
  (ApiClientFactory as jest.Mock).mockImplementation(() => ({
    getEndpointsClient: () => ({ getEndpoints: mockGetEndpoints }),
  }));
  return mockGetEndpoints;
}

function renderFilters(
  props: Partial<React.ComponentProps<typeof TestResultsFilters>> = {}
) {
  const defaults = {
    onFiltersChange: jest.fn(),
    sessionToken: 'token',
  };
  return {
    ...render(<TestResultsFilters {...defaults} {...props} />),
    ...defaults,
    ...props,
  };
}

beforeEach(() => {
  mockApiFactory();
});

afterEach(() => {
  jest.clearAllMocks();
});

describe('TestResultsFilters', () => {
  it('renders time range toggle buttons', async () => {
    mockApiFactory([makeEndpoint('ep-1', 'My Endpoint')]);
    renderFilters();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '1M' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: '3M' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '6M' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '1Y' })).toBeInTheDocument();
  });

  it('renders endpoint dropdown', async () => {
    mockApiFactory([makeEndpoint('ep-1', 'Alpha Endpoint')]);
    renderFilters();
    await waitFor(() => {
      expect(screen.getByLabelText(/endpoint/i)).toBeInTheDocument();
    });
  });

  it('calls onFiltersChange with first endpoint when loaded', async () => {
    mockApiFactory([makeEndpoint('ep-abc', 'Alpha Endpoint')]);
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });

    await waitFor(() => {
      expect(onFiltersChange).toHaveBeenCalledWith(
        expect.objectContaining({ endpointId: 'ep-abc', months: 1 })
      );
    });
  });

  it('calls onFiltersChange when a time range button is clicked', async () => {
    mockApiFactory([makeEndpoint('ep-1', 'Endpoint')]);
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '6M' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '6M' }));

    expect(onFiltersChange).toHaveBeenCalledWith(
      expect.objectContaining({ months: 6 })
    );
  });

  it('persists endpoint selection to cookie when changed', async () => {
    mockApiFactory([
      makeEndpoint('ep-1', 'Endpoint One'),
      makeEndpoint('ep-2', 'Endpoint Two'),
    ]);
    const user = userEvent.setup();
    renderFilters();

    await waitFor(() => {
      expect(screen.getByLabelText(/endpoint/i)).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText(/endpoint/i));
    await user.click(screen.getByRole('option', { name: 'Endpoint Two' }));

    expect(writeInsightsEndpointId).toHaveBeenCalledWith('ep-2');
  });

  it('does not show Reset time when months is default', async () => {
    mockApiFactory([makeEndpoint('ep-1', 'Endpoint')]);
    renderFilters();
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /reset time/i })
      ).not.toBeInTheDocument();
    });
  });

  it('shows Reset time when months is changed', async () => {
    mockApiFactory([makeEndpoint('ep-1', 'Endpoint')]);
    const user = userEvent.setup();
    renderFilters();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '3M' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '3M' }));

    expect(
      screen.getByRole('button', { name: /reset time/i })
    ).toBeInTheDocument();
  });

  it('resets months to 1M on Reset time click', async () => {
    mockApiFactory([makeEndpoint('ep-1', 'Endpoint')]);
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '1Y' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '1Y' }));
    await user.click(screen.getByRole('button', { name: /reset time/i }));

    expect(onFiltersChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ months: 1, endpointId: 'ep-1' })
    );
  });
});

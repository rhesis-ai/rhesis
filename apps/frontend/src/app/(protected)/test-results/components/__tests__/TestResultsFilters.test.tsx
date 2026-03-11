import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestResultsFilters from '../TestResultsFilters';

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn(),
}));

import { ApiClientFactory } from '@/utils/api-client/client-factory';

function makeTestSet(id: string, name: string, totalTests = 0) {
  return {
    id,
    name,
    attributes: { metadata: { total_tests: totalTests } },
  };
}

function mockApiFactory(testSets: unknown[] = []) {
  const mockGetTestSets = jest.fn().mockResolvedValue({
    data: testSets,
    pagination: { totalCount: testSets.length },
  });
  (ApiClientFactory as jest.Mock).mockImplementation(() => ({
    getTestSetsClient: () => ({ getTestSets: mockGetTestSets }),
  }));
  return mockGetTestSets;
}

function renderFilters(
  props: Partial<React.ComponentProps<typeof TestResultsFilters>> = {}
) {
  const defaults = {
    onFiltersChange: jest.fn(),
    onSearchChange: jest.fn(),
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
    renderFilters();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '1M' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: '3M' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '6M' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '1Y' })).toBeInTheDocument();
  });

  it('renders the search input', () => {
    renderFilters();
    expect(
      screen.getByPlaceholderText(/search test results/i)
    ).toBeInTheDocument();
  });

  it('calls onSearchChange when typing in the search field', async () => {
    const user = userEvent.setup();
    const onSearchChange = jest.fn();
    renderFilters({ onSearchChange });

    await user.type(
      screen.getByPlaceholderText(/search test results/i),
      'hello'
    );

    expect(onSearchChange).toHaveBeenCalledWith('h');
    expect(onSearchChange).toHaveBeenLastCalledWith('hello');
  });

  it('calls onFiltersChange when a time range button is clicked', async () => {
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });

    await user.click(screen.getByRole('button', { name: '6M' }));

    expect(onFiltersChange).toHaveBeenCalledWith(
      expect.objectContaining({ months: 6 })
    );
  });

  it('calls onFiltersChange when a different time range is selected', async () => {
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });

    await user.click(screen.getByRole('button', { name: '1Y' }));

    expect(onFiltersChange).toHaveBeenCalledWith(
      expect.objectContaining({ months: 12 })
    );
  });

  it('renders test sets in the dropdown when loaded', async () => {
    mockApiFactory([
      makeTestSet('ts-1', 'My Test Set'),
      makeTestSet('ts-2', 'Another Set'),
    ]);

    renderFilters();

    // Open the dropdown
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox'));

    await screen.findByRole('option', { name: /my test set/i });
    expect(
      screen.getByRole('option', { name: /another set/i })
    ).toBeInTheDocument();
  });

  it('shows "All Test Sets" as the default dropdown option', async () => {
    mockApiFactory([makeTestSet('ts-1', 'Test Set Alpha')]);
    renderFilters();

    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox'));

    await screen.findByRole('option', { name: /all test sets/i });
  });

  it('calls onFiltersChange with test_set_ids when a test set is selected', async () => {
    mockApiFactory([makeTestSet('ts-abc', 'Alpha Set')]);
    const onFiltersChange = jest.fn();
    renderFilters({ onFiltersChange });

    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox'));

    await screen.findByRole('option', { name: /alpha set/i });
    await user.click(screen.getByRole('option', { name: /alpha set/i }));

    expect(onFiltersChange).toHaveBeenCalledWith(
      expect.objectContaining({ test_set_ids: ['ts-abc'] })
    );
  });

  it('does not show the Reset button when no active filters', async () => {
    renderFilters();
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /reset/i })
      ).not.toBeInTheDocument();
    });
  });

  it('shows the Reset button when there is a search value', async () => {
    const user = userEvent.setup();
    renderFilters();

    await user.type(
      screen.getByPlaceholderText(/search test results/i),
      'some query'
    );

    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  it('clears the search and calls onFiltersChange with default filters on Reset click', async () => {
    const user = userEvent.setup();
    const onFiltersChange = jest.fn();
    const onSearchChange = jest.fn();
    renderFilters({ onFiltersChange, onSearchChange });

    // Trigger active filter
    await user.type(
      screen.getByPlaceholderText(/search test results/i),
      'test query'
    );

    await user.click(screen.getByRole('button', { name: /reset/i }));

    // Search field should be cleared
    expect(screen.getByPlaceholderText(/search test results/i)).toHaveValue('');

    // onFiltersChange should be called with default (months: 1)
    expect(onFiltersChange).toHaveBeenLastCalledWith({ months: 1 });

    // Reset button should disappear
    expect(
      screen.queryByRole('button', { name: /reset/i })
    ).not.toBeInTheDocument();
  });

  it('shows test counts in the dropdown when a test set has tests', async () => {
    mockApiFactory([makeTestSet('ts-1', 'Big Set', 50)]);
    renderFilters();

    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox'));

    await screen.findByText('50 tests');
  });
});

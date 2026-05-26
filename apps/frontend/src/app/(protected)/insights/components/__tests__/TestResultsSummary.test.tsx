import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import { lightTheme } from '@/styles/theme';
import TestResultsSummary from '../TestResultsSummary';
import { TestResultsClient } from '@/utils/api-client/test-results-client';

jest.mock('@/utils/api-client/test-results-client');

let mockGetStats: jest.Mock;

function makeRun(overrides: Record<string, unknown> = {}) {
  return {
    id: 'run-1',
    name: 'Test Run Alpha',
    created_at: '2026-01-15T10:00:00Z',
    total_tests: 10,
    overall: { passed: 8, failed: 2, total: 10, pass_rate: 80 },
    ...overrides,
  };
}

function makeStatsResponse(overrides: Record<string, unknown> = {}) {
  return {
    test_run_summary: [],
    metadata: { total_test_runs: 0, total_test_results: 0 },
    overall_pass_rates: { pass_rate: 0, passed: 0, failed: 0, total: 0 },
    timeline: [],
    ...overrides,
  };
}

function renderSummary(
  props: Partial<React.ComponentProps<typeof TestResultsSummary>> = {}
) {
  const defaults = {
    sessionToken: 'test-token',
    filters: { months: 1 },
  };
  return render(
    <ThemeProvider theme={lightTheme}>
      <TestResultsSummary {...defaults} {...props} />
    </ThemeProvider>
  );
}

beforeEach(() => {
  mockGetStats = jest.fn().mockResolvedValue(makeStatsResponse());
  (TestResultsClient as jest.Mock).mockImplementation(() => ({
    getComprehensiveTestResultsStats: mockGetStats,
  }));
});

afterEach(() => {
  jest.clearAllMocks();
});

describe('TestResultsSummary', () => {
  it('shows a loading spinner while fetching stats', () => {
    mockGetStats.mockImplementation(() => new Promise(() => {}));
    renderSummary();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows an error alert when the fetch fails', async () => {
    mockGetStats.mockRejectedValue(new Error('API unavailable'));
    renderSummary();
    await screen.findByText('API unavailable');
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('shows "No summary data available" when data is null', async () => {
    mockGetStats.mockResolvedValue(null);
    renderSummary();
    await screen.findByText(/no summary data available/i);
  });

  it('renders the KPI cards after loading', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 5, total_test_results: 100 },
      })
    );
    renderSummary();

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Total Test Runs')).toBeInTheDocument();
    expect(screen.getByText('Total Test Results')).toBeInTheDocument();
    expect(screen.getByText('Overall Pass Rate')).toBeInTheDocument();
    expect(screen.getByText('Total Failed Tests')).toBeInTheDocument();
  });

  it('displays the total test runs count', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 12, total_test_results: 0 },
      })
    );
    renderSummary();

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('displays the total test results count', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 0, total_test_results: 200 },
      })
    );
    renderSummary();

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('200')).toBeInTheDocument();
  });

  it('displays the overall pass rate', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 2, total_test_results: 10 },
        test_run_summary: [
          makeRun({
            total_tests: 10,
            overall: { passed: 8, failed: 2, total: 10, pass_rate: 80 },
          }),
        ],
      })
    );
    renderSummary();

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getAllByText('80.0%').length).toBeGreaterThan(0);
  });

  it('renders test run list when test_run_summary is non-empty', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 1, total_test_results: 10 },
        test_run_summary: [makeRun({ id: 'run-1', name: 'My Alpha Run' })],
      })
    );
    renderSummary();

    await screen.findByText('My Alpha Run');
    expect(screen.getByText('Test Runs (1)')).toBeInTheDocument();
  });

  it('renders pass/fail counts per test run', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 1, total_test_results: 10 },
        test_run_summary: [
          makeRun({
            total_tests: 10,
            overall: { passed: 7, failed: 3, total: 10, pass_rate: 70 },
          }),
        ],
      })
    );
    renderSummary();

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getAllByText('7').length).toBeGreaterThan(0);
    expect(screen.getAllByText('3').length).toBeGreaterThan(0);
  });

  it('filters test runs by search value', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 2, total_test_results: 20 },
        test_run_summary: [
          makeRun({ id: 'run-1', name: 'Alpha Run' }),
          makeRun({ id: 'run-2', name: 'Beta Run' }),
        ],
      })
    );
    renderSummary({ searchValue: 'alpha' });

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Alpha Run')).toBeInTheDocument();
    expect(screen.queryByText('Beta Run')).not.toBeInTheDocument();
  });

  it('shows "No test runs match your search" when all runs are filtered out', async () => {
    mockGetStats.mockResolvedValue(
      makeStatsResponse({
        metadata: { total_test_runs: 1, total_test_results: 10 },
        test_run_summary: [makeRun({ id: 'run-1', name: 'Alpha Run' })],
      })
    );
    renderSummary({ searchValue: 'zzznomatch' });

    await screen.findByText(/no test runs match your search/i);
  });

  it('re-fetches when filters prop changes', async () => {
    mockGetStats.mockResolvedValue(makeStatsResponse());

    const { rerender } = renderSummary({ filters: { months: 1 } });

    await waitFor(() => expect(mockGetStats).toHaveBeenCalledTimes(1));

    rerender(
      <ThemeProvider theme={lightTheme}>
        <TestResultsSummary sessionToken="test-token" filters={{ months: 6 }} />
      </ThemeProvider>
    );

    await waitFor(() => expect(mockGetStats).toHaveBeenCalledTimes(2));
    expect(mockGetStats).toHaveBeenLastCalledWith(
      expect.objectContaining({ months: 6 })
    );
  });
});

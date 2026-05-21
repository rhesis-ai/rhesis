import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestRunPerformance from '../TestRunPerformance';

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn(),
}));

jest.mock('@/components/icons', () => ({
  CategoryIcon: (props: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="category-icon" {...props} />
  ),
}));

jest.mock('@/components/common/TestRunStatus', () => ({
  getTestRunStatusColor: jest.fn(() => 'success'),
  getTestRunStatusIcon: jest.fn(() => <span />),
}));

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
  useSearchParams: jest.fn(() => new URLSearchParams()),
  usePathname: jest.fn(() => '/'),
}));

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter } from 'next/navigation';

function makeTestRun(overrides: Record<string, unknown> = {}) {
  return {
    id: 'run-1',
    name: 'My Test Run',
    status: { name: 'completed' },
    created_at: new Date().toISOString(),
    attributes: {},
    test_configuration: {
      test_set: {
        id: 'ts-1',
        name: 'My Test Set',
        test_set_type: { type_value: 'standard' },
        attributes: { metadata: { total_tests: 10 } },
      },
    },
    stats: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
    ...overrides,
  };
}

function mockApiClientFactory(
  testRuns: unknown[] = [],
  withStatsError = false
) {
  const mockGetTestRuns = jest.fn().mockResolvedValue({
    data: testRuns,
    pagination: { totalCount: testRuns.length },
  });

  const testRunSummary = testRuns
    .filter((run: any) => run.stats)
    .map((run: any) => ({ id: run.id, overall: run.stats }));

  const mockGetStats = withStatsError
    ? jest.fn().mockRejectedValue(new Error('Stats unavailable'))
    : jest.fn().mockResolvedValue({ test_run_summary: testRunSummary });

  (ApiClientFactory as jest.Mock).mockImplementation(() => ({
    getTestRunsClient: () => ({ getTestRuns: mockGetTestRuns }),
    getTestResultsClient: () => ({
      getComprehensiveTestResultsStats: mockGetStats,
    }),
  }));

  return { mockGetTestRuns, mockGetStats };
}

beforeEach(() => {
  // jsdom doesn't set window.innerHeight by default; provide a value
  Object.defineProperty(window, 'innerHeight', {
    writable: true,
    configurable: true,
    value: 900,
  });
  (useRouter as jest.Mock).mockReturnValue({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  });
  mockApiClientFactory();
});

afterEach(() => {
  jest.clearAllMocks();
});

describe('TestRunPerformance', () => {
  it('shows a loading spinner while fetching test runs', () => {
    (ApiClientFactory as jest.Mock).mockImplementation(() => ({
      getTestRunsClient: () => ({
        getTestRuns: jest.fn(() => new Promise(() => {})),
      }),
      getTestResultsClient: () => ({
        getComprehensiveTestResultsStats: jest.fn(() => new Promise(() => {})),
      }),
    }));

    render(<TestRunPerformance sessionToken="token" />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('renders the "Recent Test Runs" heading after loading', async () => {
    mockApiClientFactory([]);
    render(<TestRunPerformance sessionToken="token" />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Recent Test Runs')).toBeInTheDocument();
  });

  it('shows "No test runs" when the API returns an empty list', async () => {
    mockApiClientFactory([]);
    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('No test runs');
  });

  it('renders test run cards for each test run returned', async () => {
    mockApiClientFactory([
      makeTestRun({ id: 'run-1', name: 'Alpha Run' }),
      makeTestRun({ id: 'run-2', name: 'Beta Run' }),
    ]);

    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('Alpha Run');
    expect(screen.getByText('Beta Run')).toBeInTheDocument();
  });

  it('shows pass rate and test counts for a test run', async () => {
    mockApiClientFactory([
      makeTestRun({
        id: 'run-1',
        name: 'Pass Rate Test',
        stats: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
      }),
    ]);

    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('Pass Rate Test');
    expect(screen.getByText('80.0%')).toBeInTheDocument();
    expect(screen.getByText('8 passed')).toBeInTheDocument();
    expect(screen.getByText('2 failed')).toBeInTheDocument();
  });

  it('shows the test set name as a link when available', async () => {
    mockApiClientFactory([makeTestRun({ id: 'run-1', name: 'Test' })]);

    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('My Test Set');
    const link = screen.getByRole('link', { name: /my test set/i });
    expect(link).toHaveAttribute('href', '/test-sets/ts-1');
  });

  it('navigates to the test run detail page when a card is clicked', async () => {
    const mockPush = jest.fn();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });

    mockApiClientFactory([
      makeTestRun({ id: 'run-123', name: 'Clickable Run' }),
    ]);

    const user = userEvent.setup();
    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('Clickable Run');
    await user.click(screen.getByText('Clickable Run'));

    expect(mockPush).toHaveBeenCalledWith('/test-runs/run-123');
  });

  it('navigates to /test-runs when "View All" is clicked', async () => {
    const mockPush = jest.fn();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });

    mockApiClientFactory([]);
    const user = userEvent.setup();
    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('View All');
    await user.click(screen.getByRole('button', { name: /view all/i }));

    expect(mockPush).toHaveBeenCalledWith('/test-runs');
  });

  it('shows an error alert when the API call fails', async () => {
    (ApiClientFactory as jest.Mock).mockImplementation(() => ({
      getTestRunsClient: () => ({
        getTestRuns: jest.fn().mockRejectedValue(new Error('Network error')),
      }),
      getTestResultsClient: () => ({
        getComprehensiveTestResultsStats: jest.fn(),
      }),
    }));

    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText(/unable to load test run data/i);
  });

  it('calls onLoadComplete callback after data loads', async () => {
    const onLoadComplete = jest.fn();
    mockApiClientFactory([]);

    render(
      <TestRunPerformance
        sessionToken="token"
        onLoadComplete={onLoadComplete}
      />
    );

    await waitFor(() => {
      expect(onLoadComplete).toHaveBeenCalled();
    });
  });

  it('gracefully handles missing stats for a test run', async () => {
    mockApiClientFactory(
      [makeTestRun({ id: 'run-1', name: 'No Stats Run', stats: null })],
      true
    );

    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('No Stats Run');
    // Should render without crashing even when stats are null
    expect(screen.getByText('No Stats Run')).toBeInTheDocument();
  });

  it('shows "tests" label for test counts', async () => {
    mockApiClientFactory([
      makeTestRun({
        id: 'run-1',
        name: 'Count Test',
        stats: { total: 5, passed: 3, failed: 2, pass_rate: 60 },
        test_configuration: {
          test_set: {
            id: 'ts-1',
            name: 'Test Set',
            test_set_type: null,
            attributes: { metadata: { total_tests: 5 } },
          },
        },
      }),
    ]);

    render(<TestRunPerformance sessionToken="token" />);

    await screen.findByText('Count Test');
    expect(screen.getByText('5 tests')).toBeInTheDocument();
  });
});

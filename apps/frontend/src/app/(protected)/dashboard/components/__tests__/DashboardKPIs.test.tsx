import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import DashboardKPIs from '../DashboardKPIs';

jest.mock('@mui/x-charts/SparkLineChart', () => ({
  SparkLineChart: () => <div data-testid="sparkline-chart" />,
}));

jest.mock('@mui/x-charts/Gauge', () => ({
  Gauge: () => <div data-testid="gauge" />,
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn(),
}));

import { ApiClientFactory } from '@/utils/api-client/client-factory';

const makeTestStats = (total = 0, monthlyHistory = {}) => ({
  total,
  history: { monthly_counts: monthlyHistory },
});

const makeTestResultsStats = (passRate = 0, timeline: unknown[] = []) => ({
  overall_pass_rates: { pass_rate: passRate, passed: 0, failed: 0, total: 0 },
  timeline,
});

const makeTestSetStats = (total = 0, monthlyHistory = {}) => ({
  total,
  history: { monthly_counts: monthlyHistory },
});

function mockApiClientFactory(overrides: Record<string, jest.Mock> = {}) {
  const mockGetTestStats = jest.fn().mockResolvedValue(makeTestStats());
  const mockGetTestResultsStats = jest
    .fn()
    .mockResolvedValue(makeTestResultsStats());
  const mockGetTestSetStats = jest.fn().mockResolvedValue(makeTestSetStats());

  (ApiClientFactory as jest.Mock).mockImplementation(() => ({
    getTestsClient: () => ({ getTestStats: mockGetTestStats }),
    getTestResultsClient: () => ({
      getComprehensiveTestResultsStats: mockGetTestResultsStats,
    }),
    getTestSetsClient: () => ({ getTestSetStats: mockGetTestSetStats }),
    ...overrides,
  }));

  return { mockGetTestStats, mockGetTestResultsStats, mockGetTestSetStats };
}

describe('DashboardKPIs', () => {
  beforeEach(() => {
    mockApiClientFactory();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('shows a loading spinner while fetching KPIs', () => {
    // Hang the API call to keep loading state
    (ApiClientFactory as jest.Mock).mockImplementation(() => ({
      getTestsClient: () => ({
        getTestStats: jest.fn(() => new Promise(() => {})),
      }),
      getTestResultsClient: () => ({
        getComprehensiveTestResultsStats: jest.fn(() => new Promise(() => {})),
      }),
      getTestSetsClient: () => ({
        getTestSetStats: jest.fn(() => new Promise(() => {})),
      }),
    }));

    render(<DashboardKPIs sessionToken="token" />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('renders KPI cards after loading', async () => {
    render(<DashboardKPIs sessionToken="token" />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Overall Pass Rate')).toBeInTheDocument();
    expect(screen.getByText('Test Executions')).toBeInTheDocument();
    expect(screen.getByText('Test Sets')).toBeInTheDocument();
    expect(screen.getByText('Tests')).toBeInTheDocument();
  });

  it('displays total test count from API', async () => {
    (ApiClientFactory as jest.Mock).mockImplementation(() => ({
      getTestsClient: () => ({
        getTestStats: jest.fn().mockResolvedValue(makeTestStats(42)),
      }),
      getTestResultsClient: () => ({
        getComprehensiveTestResultsStats: jest
          .fn()
          .mockResolvedValue(makeTestResultsStats()),
      }),
      getTestSetsClient: () => ({
        getTestSetStats: jest.fn().mockResolvedValue(makeTestSetStats()),
      }),
    }));

    render(<DashboardKPIs sessionToken="token" />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('displays total test sets count from API', async () => {
    (ApiClientFactory as jest.Mock).mockImplementation(() => ({
      getTestsClient: () => ({
        getTestStats: jest.fn().mockResolvedValue(makeTestStats(0)),
      }),
      getTestResultsClient: () => ({
        getComprehensiveTestResultsStats: jest
          .fn()
          .mockResolvedValue(makeTestResultsStats()),
      }),
      getTestSetsClient: () => ({
        getTestSetStats: jest.fn().mockResolvedValue(makeTestSetStats(7)),
      }),
    }));

    render(<DashboardKPIs sessionToken="token" />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('shows "No test executions" when test execution count is 0', async () => {
    render(<DashboardKPIs sessionToken="token" />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('No test executions')).toBeInTheDocument();
  });

  it('shows "No test runs" when there are no pass/fail results', async () => {
    render(<DashboardKPIs sessionToken="token" />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    expect(screen.getByText('No test runs')).toBeInTheDocument();
  });

  it('calls onLoadComplete callback after fetching', async () => {
    const onLoadComplete = jest.fn();
    render(
      <DashboardKPIs sessionToken="token" onLoadComplete={onLoadComplete} />
    );

    await waitFor(() => {
      expect(onLoadComplete).toHaveBeenCalled();
    });
  });

  it('does not fetch when sessionToken is empty', () => {
    const { mockGetTestStats } = mockApiClientFactory();
    render(<DashboardKPIs sessionToken="" />);

    expect(mockGetTestStats).not.toHaveBeenCalled();
  });

  it('shows pass rate percentage from API', async () => {
    (ApiClientFactory as jest.Mock).mockImplementation(() => ({
      getTestsClient: () => ({
        getTestStats: jest.fn().mockResolvedValue(makeTestStats(0)),
      }),
      getTestResultsClient: () => ({
        getComprehensiveTestResultsStats: jest.fn().mockResolvedValue({
          overall_pass_rates: null,
          timeline: [
            {
              date: '2026-01',
              overall: { pass_rate: 85.5, passed: 171, failed: 29, total: 200 },
            },
          ],
        }),
      }),
      getTestSetsClient: () => ({
        getTestSetStats: jest.fn().mockResolvedValue(makeTestSetStats()),
      }),
    }));

    render(<DashboardKPIs sessionToken="token" />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    // Pass rate is shown as "{value}%"
    expect(screen.getByText('85.5%')).toBeInTheDocument();
  });
});

import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import '@testing-library/jest-dom';

import { useUsageForPeriod } from '../useUsageForPeriod';
import { useUsage } from '@/contexts/UsageContext';

const mockGetUsage = jest.fn();

const AUTHENTICATED_SESSION = {
  data: { user: { id: 'user-1' } },
  status: 'authenticated',
};

let mockSession: { data: unknown; status: string } = AUTHENTICATED_SESSION;

jest.mock('next-auth/react', () => ({
  useSession: () => mockSession,
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getUsageClient: () => ({
      getUsage: mockGetUsage,
    }),
  })),
}));

jest.mock('@/contexts/UsageContext', () => ({
  useUsage: jest.fn(),
}));

const mockUseUsage = useUsage as jest.Mock;

const CURRENT_STATE = {
  resources: { test_executions: { used: 1, limit: 100 } },
  edition: 'community',
  loading: false,
  error: null,
};

beforeEach(() => {
  mockGetUsage.mockReset();
  mockSession = AUTHENTICATED_SESSION;
  mockUseUsage.mockReset();
  mockUseUsage.mockReturnValue(CURRENT_STATE);
});

function Probe({ periodStart }: { periodStart: string | null }) {
  const { resources, loading, error } = useUsageForPeriod(periodStart);
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="error">{error?.message ?? 'none'}</div>
      <div data-testid="resources">{JSON.stringify(resources)}</div>
    </div>
  );
}

describe('useUsageForPeriod', () => {
  it('delegates to UsageContext when periodStart is null', () => {
    render(<Probe periodStart={null} />);

    expect(screen.getByTestId('resources')).toHaveTextContent(
      'test_executions'
    );
    expect(mockGetUsage).not.toHaveBeenCalled();
  });

  it('fetches a specific period when periodStart is given', async () => {
    mockGetUsage.mockResolvedValue({
      resources: { test_executions: { used: 42, limit: 100 } },
      edition: 'community',
    });

    render(<Probe periodStart="2026-07-01" />);

    await waitFor(() =>
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    );
    expect(mockGetUsage).toHaveBeenCalledWith('2026-07-01');
    expect(screen.getByTestId('resources')).toHaveTextContent('42');
  });

  it('fails closed on fetch error for a past period', async () => {
    mockGetUsage.mockRejectedValue(new Error('boom'));

    render(<Probe periodStart="2026-07-01" />);

    await waitFor(() =>
      expect(screen.getByTestId('error')).toHaveTextContent('boom')
    );
    expect(screen.getByTestId('resources')).toHaveTextContent('{}');
  });

  it('re-fetches when periodStart changes', async () => {
    mockGetUsage.mockResolvedValue({ resources: {}, edition: 'community' });

    const { rerender } = render(<Probe periodStart="2026-07-01" />);
    await waitFor(() =>
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    );

    rerender(<Probe periodStart="2026-06-01" />);

    await waitFor(() =>
      expect(mockGetUsage).toHaveBeenCalledWith('2026-06-01')
    );
    expect(mockGetUsage).toHaveBeenCalledWith('2026-07-01');
  });
});

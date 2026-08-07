import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import '@testing-library/jest-dom';

import { useUsageHistory } from '../useUsageHistory';

const mockGetUsageHistory = jest.fn();

const AUTHENTICATED_SESSION = {
  data: { user: { id: 'user-1' } },
  status: 'authenticated',
};

// Mutable so individual tests can simulate an unauthenticated/loading session.
let mockSession: { data: unknown; status: string } = AUTHENTICATED_SESSION;

jest.mock('next-auth/react', () => ({
  useSession: () => mockSession,
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getUsageClient: () => ({
      getUsageHistory: mockGetUsageHistory,
    }),
  })),
}));

beforeEach(() => {
  mockGetUsageHistory.mockReset();
  mockSession = AUTHENTICATED_SESSION;
});

function Probe({ months }: { months: number }) {
  const { resources, loading, error } = useUsageHistory(months);
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="error">{error?.message ?? 'none'}</div>
      <div data-testid="resources">{JSON.stringify(resources)}</div>
    </div>
  );
}

describe('useUsageHistory', () => {
  it('fetches history for the given months and exposes the resources', async () => {
    mockGetUsageHistory.mockResolvedValue({
      resources: {
        test_executions: [{ period_start: '2026-06-01', used: 3 }],
      },
    });

    render(<Probe months={6} />);

    await waitFor(() =>
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    );
    expect(mockGetUsageHistory).toHaveBeenCalledWith(6);
    expect(screen.getByTestId('resources')).toHaveTextContent(
      'test_executions'
    );
  });

  it('reports loading while the session is still resolving', () => {
    mockSession = { data: null, status: 'loading' };
    mockGetUsageHistory.mockResolvedValue({ resources: {} });

    render(<Probe months={6} />);

    expect(screen.getByTestId('loading')).toHaveTextContent('true');
    expect(mockGetUsageHistory).not.toHaveBeenCalled();
  });

  it('fails closed on fetch error (empty resources, error surfaced)', async () => {
    mockGetUsageHistory.mockRejectedValue(new Error('boom'));

    render(<Probe months={6} />);

    await waitFor(() =>
      expect(screen.getByTestId('error')).toHaveTextContent('boom')
    );
    expect(screen.getByTestId('loading')).toHaveTextContent('false');
    expect(screen.getByTestId('resources')).toHaveTextContent('{}');
  });

  it('re-fetches when months changes', async () => {
    mockGetUsageHistory.mockResolvedValue({ resources: {} });

    const { rerender } = render(<Probe months={6} />);
    await waitFor(() =>
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    );

    rerender(<Probe months={12} />);

    await waitFor(() => expect(mockGetUsageHistory).toHaveBeenCalledWith(12));
    expect(mockGetUsageHistory).toHaveBeenCalledWith(6);
  });
});

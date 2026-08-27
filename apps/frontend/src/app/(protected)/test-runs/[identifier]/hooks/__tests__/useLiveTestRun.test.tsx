import React from 'react';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { testRunKeys } from '@/constants/query-keys';
import { useLiveTestRun } from '../useLiveTestRun';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

const mockGetTestRun = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestRunsClient: () => ({
      getTestRun: mockGetTestRun,
    }),
  })),
}));

function makeTestRun(overrides: Partial<TestRunDetail> = {}): TestRunDetail {
  return {
    id: 'run-1',
    name: 'Test Run 1',
    status: { name: 'Progress' },
    attributes: {},
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as TestRunDetail;
}

describe('useLiveTestRun', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the server-fetched testRun immediately, with no extra fetch', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const initial = makeTestRun();
    const { result } = renderHook(() => useLiveTestRun('run-1', initial), {
      wrapper,
    });

    expect(result.current).toBe(initial);
    expect(mockGetTestRun).not.toHaveBeenCalled();
  });

  it('reflects a status transition once the query refetches', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const initial = makeTestRun({
      status: {
        id: '00000000-0000-0000-0000-000000000001',
        name: 'Progress',
      },
    });
    mockGetTestRun.mockResolvedValue(
      makeTestRun({
        status: {
          id: '00000000-0000-0000-0000-000000000002',
          name: 'Completed',
        },
      })
    );

    const { result } = renderHook(() => useLiveTestRun('run-1', initial), {
      wrapper,
    });

    expect(result.current.status?.name).toBe('Progress');

    // Bypass the interval's own timing (fake timers and react-query's
    // internal scheduler don't play well together) and trigger the same
    // refetch path a poll or a WebSocket-driven invalidation would.
    await act(async () => {
      await queryClient.invalidateQueries({
        queryKey: testRunKeys.detail('run-1'),
      });
    });

    await waitFor(() => expect(result.current.status?.name).toBe('Completed'));
  });
});

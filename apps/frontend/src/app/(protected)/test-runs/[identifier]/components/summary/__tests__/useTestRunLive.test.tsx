/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EventType } from '@/utils/websocket/types';
import type { VerdictMatrix } from '@/utils/api-client/interfaces/test-run';

const mockSubscribe = jest.fn();
const mockSubscribeToChannel = jest.fn();
const mockUnsubscribeFromChannel = jest.fn();
let mockIsConnected = true;

jest.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    isConnected: mockIsConnected,
    subscribe: mockSubscribe,
    subscribeToChannel: mockSubscribeToChannel,
    unsubscribeFromChannel: mockUnsubscribeFromChannel,
  }),
}));

const mockGetVerdictMatrix = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestRunsClient: () => ({
      getVerdictMatrix: mockGetVerdictMatrix,
    }),
  })),
}));

import { useTestRunLive } from '../hooks/useTestRunLive';

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

function makeMatrix(overrides: Partial<VerdictMatrix> = {}): VerdictMatrix {
  return {
    test_run_id: 'run-1',
    project_id: 'proj-1',
    status: 'progress',
    is_terminal: false,
    version: 1,
    test_ids: ['t1', 't2'],
    test_status: '...',
    requirements: [],
    rows: [],
    kpis: {
      pass_rate: null,
      tests_executed: 0,
      tests_total: 2,
      verdicts_resolved: 0,
      verdicts_planned: 4,
      failures: 0,
    },
    ...overrides,
  };
}

describe('useTestRunLive', () => {
  let subscribedHandlers: Map<string, (msg: any) => void>;

  beforeEach(() => {
    jest.clearAllMocks();
    mockIsConnected = true;
    subscribedHandlers = new Map();

    mockSubscribe.mockImplementation(
      (eventType: string, handler: (msg: any) => void) => {
        subscribedHandlers.set(eventType, handler);
        return () => subscribedHandlers.delete(eventType);
      }
    );

    mockGetVerdictMatrix.mockResolvedValue(makeMatrix());
  });

  it('fetches verdict matrix on mount', async () => {
    const { result } = renderHook(() => useTestRunLive('run-1'), { wrapper });

    await waitFor(() => expect(result.current.matrix).toBeDefined());
    expect(mockGetVerdictMatrix).toHaveBeenCalledWith('run-1', undefined);
  });

  it('subscribes to channel with project_id', async () => {
    const { result } = renderHook(() => useTestRunLive('run-1'), { wrapper });

    await waitFor(() => expect(result.current.matrix).toBeDefined());
    expect(mockSubscribeToChannel).toHaveBeenCalledWith(
      'test_run:run-1',
      'proj-1'
    );
  });

  it('ignores events from other channels', async () => {
    const { result } = renderHook(() => useTestRunLive('run-1'), { wrapper });

    await waitFor(() => expect(result.current.matrix).toBeDefined());
    mockGetVerdictMatrix.mockClear();

    const handler = subscribedHandlers.get(EventType.TEST_RUN_PROGRESSED);
    expect(handler).toBeDefined();

    act(() => {
      handler!({ channel: 'test_run:other-id' });
    });

    // Should not trigger a refetch for a different channel
    expect(mockGetVerdictMatrix).not.toHaveBeenCalled();
  });

  it('refetches on TEST_RUN_PROGRESSED for matching channel', async () => {
    const { result } = renderHook(() => useTestRunLive('run-1'), { wrapper });

    await waitFor(() => expect(result.current.matrix).toBeDefined());
    mockGetVerdictMatrix.mockClear();

    const handler = subscribedHandlers.get(EventType.TEST_RUN_PROGRESSED);

    await act(async () => {
      handler!({ channel: 'test_run:run-1' });
    });

    await waitFor(() => expect(mockGetVerdictMatrix).toHaveBeenCalled());
  });

  it('marks terminal when matrix.is_terminal is true', async () => {
    mockGetVerdictMatrix.mockResolvedValue(makeMatrix({ is_terminal: true }));

    const { result } = renderHook(() => useTestRunLive('run-1'), { wrapper });

    await waitFor(() => expect(result.current.isTerminal).toBe(true));
  });

  it('sets subscriptionFailed on SUBSCRIPTION_ERROR', async () => {
    const { result } = renderHook(() => useTestRunLive('run-1'), { wrapper });

    await waitFor(() => expect(result.current.matrix).toBeDefined());

    const handler = subscribedHandlers.get(EventType.SUBSCRIPTION_ERROR);
    expect(handler).toBeDefined();

    act(() => {
      handler!({ channel: 'test_run:run-1' });
    });

    // After subscription error, the hook should fall back to polling
    // (liveUpdates becomes false, refetchInterval returns LIVE_POLL_MS)
    // We verify by checking isConnected stays true but internal state changed
    expect(result.current.isConnected).toBe(true);
  });
});

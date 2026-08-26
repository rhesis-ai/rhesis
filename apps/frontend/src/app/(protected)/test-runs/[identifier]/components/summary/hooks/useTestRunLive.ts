'use client';

import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { EventType } from '@/utils/websocket/types';
import type { VerdictMatrix } from '@/utils/api-client/interfaces/test-run';

const LIVE_POLL_MS = 3000;

export function useTestRunLive(testRunId: string): {
  matrix: VerdictMatrix | undefined;
  isLoading: boolean;
  isTerminal: boolean;
  isConnected: boolean;
} {
  const queryClient = useQueryClient();
  const { isConnected, subscribe, subscribeToChannel, unsubscribeFromChannel } =
    useWebSocketContext();

  const [subscriptionFailed, setSubscriptionFailed] = useState(false);
  useEffect(() => setSubscriptionFailed(false), [testRunId]);

  const liveUpdates = isConnected && !subscriptionFailed;
  const channel = `test_run:${testRunId}`;

  // After the first full fetch (with test_ids), subsequent refetches use
  // ?columns=none to skip the test_ids array (client already has them).
  // Reset per testRunId so switching runs without a remount still fetches
  // the new run's test_ids on its first request.
  const hasFetched = useRef(false);
  useEffect(() => {
    hasFetched.current = false;
  }, [testRunId]);

  const { data: matrix, isLoading } = useQuery<VerdictMatrix>({
    queryKey: ['test-runs', 'verdict-matrix', testRunId],
    queryFn: async () => {
      const client = new ApiClientFactory().getTestRunsClient();
      const columns = hasFetched.current ? 'none' : undefined;
      const result = await client.getVerdictMatrix(testRunId, columns);
      hasFetched.current = true;
      return result;
    },
    refetchInterval: query => {
      if (query.state.data?.is_terminal) return false;
      if (liveUpdates) return false;
      return LIVE_POLL_MS;
    },
  });

  // Subscribe to the channel once we have the project_id.
  useEffect(() => {
    if (!matrix?.project_id || !isConnected) return;
    subscribeToChannel(channel, matrix.project_id);
    return () => {
      unsubscribeFromChannel(channel);
    };
  }, [
    matrix?.project_id,
    isConnected,
    channel,
    subscribeToChannel,
    unsubscribeFromChannel,
  ]);

  // Handle WebSocket events.
  useEffect(() => {
    const forThisRun =
      (handler: () => void) =>
      (msg: { channel?: string | null }): void => {
        if (msg.channel === channel) handler();
      };

    const unsubProgress = subscribe(
      EventType.TEST_RUN_PROGRESSED,
      forThisRun(() =>
        queryClient.invalidateQueries({
          queryKey: ['test-runs', 'verdict-matrix', testRunId],
        })
      )
    );
    const unsubError = subscribe(
      EventType.SUBSCRIPTION_ERROR,
      forThisRun(() => setSubscriptionFailed(true))
    );
    return () => {
      unsubProgress();
      unsubError();
    };
  }, [testRunId, channel, subscribe, queryClient]);

  // On reconnect, re-fetch immediately.
  const prevConnected = useRef(isConnected);
  useEffect(() => {
    if (isConnected && !prevConnected.current) {
      void queryClient.invalidateQueries({
        queryKey: ['test-runs', 'verdict-matrix', testRunId],
      });
    }
    prevConnected.current = isConnected;
  }, [isConnected, testRunId, queryClient]);

  return {
    matrix,
    isLoading,
    isTerminal: matrix?.is_terminal ?? false,
    isConnected,
  };
}

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';
import { isEmbeddingGraphNewerThanBaseline } from '@/utils/embedding/embeddingGraphPolling';

const POLL_INTERVAL_MS = 2500;
const MAX_POLL_ATTEMPTS = 120;

export interface UseEmbeddingGraphResult {
  graph: Scatter2DGraph | null;
  isLoading: boolean;
  isComputing: boolean;
  error: string | null;
  computeGraph: () => Promise<void>;
  refresh: () => Promise<void>;
}

export function useEmbeddingGraph(
  testSetId: string,
  sessionToken: string,
  options?: { enabled?: boolean }
): UseEmbeddingGraphResult {
  const enabled = options?.enabled ?? true;
  const [graph, setGraph] = useState<Scatter2DGraph | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isComputing, setIsComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttemptsRef = useRef(0);
  /** Set when compute/recompute starts; poll until graph computed_at is newer. */
  const computeBaselineRef = useRef<string | null>(null);

  const resetPollTimer = useCallback(() => {
    if (pollTimeoutRef.current !== null) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    pollAttemptsRef.current = 0;
  }, []);

  const clearPoll = useCallback(() => {
    resetPollTimer();
    computeBaselineRef.current = null;
  }, [resetPollTimer]);

  const fetchGraph = useCallback(
    async (options?: {
      waitForNewerThanBaseline: boolean;
    }): Promise<'ready' | 'pending'> => {
      const client = new ApiClientFactory(sessionToken).getTestSetsClient();
      const response = await client.getEmbeddingGraph(testSetId);
      if (response.status === 'ready') {
        if (
          options?.waitForNewerThanBaseline &&
          !isEmbeddingGraphNewerThanBaseline(
            response.graph.computed_at,
            computeBaselineRef.current
          )
        ) {
          return 'pending';
        }
        setGraph(response.graph);
        return 'ready';
      }
      return 'pending';
    },
    [sessionToken, testSetId]
  );

  const pollUntilReady = useCallback(() => {
    resetPollTimer();
    setIsComputing(true);

    const poll = async () => {
      pollAttemptsRef.current += 1;
      try {
        const status = await fetchGraph({ waitForNewerThanBaseline: true });
        if (status === 'ready') {
          setIsComputing(false);
          clearPoll();
          return;
        }
        if (pollAttemptsRef.current >= MAX_POLL_ATTEMPTS) {
          setError('Embedding map computation timed out. Please try again.');
          setIsComputing(false);
          clearPoll();
          return;
        }
        pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load embedding map';
        setError(message);
        setIsComputing(false);
        clearPoll();
      }
    };

    void poll();
  }, [clearPoll, fetchGraph, resetPollTimer]);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      await fetchGraph();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load embedding map';
      setError(message);
    }
  }, [fetchGraph]);

  const computeGraph = useCallback(async () => {
    setError(null);
    computeBaselineRef.current = graph?.computed_at ?? null;
    setIsComputing(true);
    try {
      const client = new ApiClientFactory(sessionToken).getTestSetsClient();
      await client.computeEmbeddingGraph(testSetId);
      pollUntilReady();
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : 'Failed to start embedding map computation';
      setError(message);
      setIsComputing(false);
      computeBaselineRef.current = null;
    }
  }, [graph?.computed_at, pollUntilReady, sessionToken, testSetId]);

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const status = await fetchGraph();
        if (!cancelled && status === 'pending') {
          setGraph(null);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : 'Failed to load embedding map';
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
      clearPoll();
    };
  }, [clearPoll, enabled, fetchGraph]);

  return {
    graph,
    isLoading,
    isComputing,
    error,
    computeGraph,
    refresh,
  };
}

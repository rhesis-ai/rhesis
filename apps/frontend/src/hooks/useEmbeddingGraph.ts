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
  /** Bumped to cancel in-flight polls (disable, unmount, or new poll session). */
  const pollGenerationRef = useRef(0);
  /** Set when compute/recompute starts; poll until graph computed_at is newer. */
  const computeBaselineRef = useRef<string | null>(null);

  const resetPollTimer = useCallback(() => {
    if (pollTimeoutRef.current !== null) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    pollAttemptsRef.current = 0;
  }, []);

  const invalidatePollSession = useCallback(() => {
    pollGenerationRef.current += 1;
  }, []);

  const stopPolling = useCallback(() => {
    invalidatePollSession();
    resetPollTimer();
    setIsComputing(false);
  }, [invalidatePollSession, resetPollTimer]);

  const clearPoll = useCallback(() => {
    stopPolling();
    computeBaselineRef.current = null;
  }, [stopPolling]);

  const fetchGraph = useCallback(
    async (options?: {
      waitForNewerThanBaseline: boolean;
      pollGeneration?: number;
    }): Promise<
      { status: 'ready'; graph: Scatter2DGraph } | { status: 'pending' }
    > => {
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
          return { status: 'pending' };
        }
        if (
          options?.pollGeneration !== undefined &&
          pollGenerationRef.current !== options.pollGeneration
        ) {
          return { status: 'pending' };
        }
        setGraph(response.graph);
        return { status: 'ready', graph: response.graph };
      }
      return { status: 'pending' };
    },
    [sessionToken, testSetId]
  );

  const pollUntilReady = useCallback(() => {
    resetPollTimer();
    invalidatePollSession();
    const pollGeneration = pollGenerationRef.current;
    setIsComputing(true);

    const isPollSessionActive = () =>
      pollGenerationRef.current === pollGeneration;

    const poll = async () => {
      if (!isPollSessionActive()) {
        return;
      }

      pollAttemptsRef.current += 1;
      try {
        const result = await fetchGraph({
          waitForNewerThanBaseline: true,
          pollGeneration,
        });
        if (!isPollSessionActive()) {
          return;
        }
        if (result.status === 'ready') {
          clearPoll();
          return;
        }
        if (pollAttemptsRef.current >= MAX_POLL_ATTEMPTS) {
          setError('Embedding map computation timed out. Please try again.');
          clearPoll();
          return;
        }
        if (!isPollSessionActive()) {
          return;
        }
        pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (!isPollSessionActive()) {
          return;
        }
        const message =
          err instanceof Error ? err.message : 'Failed to load embedding map';
        setError(message);
        clearPoll();
      }
    };

    void poll();
  }, [clearPoll, fetchGraph, invalidatePollSession, resetPollTimer]);

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
      clearPoll();
    }
  }, [clearPoll, graph?.computed_at, pollUntilReady, sessionToken, testSetId]);

  useEffect(() => {
    clearPoll();
  }, [clearPoll, sessionToken, testSetId]);

  useEffect(() => {
    if (!enabled) {
      stopPolling();
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await fetchGraph();
        if (cancelled) return;

        if (result.status === 'pending') {
          setGraph(null);
          pollUntilReady();
          return;
        }

        const baseline = computeBaselineRef.current;
        if (
          baseline !== null &&
          !isEmbeddingGraphNewerThanBaseline(result.graph.computed_at, baseline)
        ) {
          pollUntilReady();
          return;
        }

        if (baseline !== null) {
          computeBaselineRef.current = null;
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
      stopPolling();
    };
  }, [enabled, fetchGraph, pollUntilReady, stopPolling]);

  return {
    graph,
    isLoading,
    isComputing,
    error,
    computeGraph,
    refresh,
  };
}

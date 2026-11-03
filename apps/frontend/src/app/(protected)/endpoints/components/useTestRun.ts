'use client';

import { useCallback, useRef, useState } from 'react';
import type { EndpointTestResult } from './TestResponseCard';

/** A test that took longer than this marks the API as slow (no more auto re-sends). */
export const SLOW_API_MS = 10_000;

/**
 * One test request at a time on screen. Each run gets an id; an answer that
 * arrives after a newer run (or a cancel) started is dropped, so a slow
 * earlier call can't overwrite a newer result or end the "waiting" state.
 */
export function useTestRun() {
  const [result, setResult] = useState<EndpointTestResult | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [lastDurationMs, setLastDurationMs] = useState<number | null>(null);
  const runId = useRef(0);
  const startedAtRef = useRef<number | null>(null);

  const run = useCallback(
    async (call: () => Promise<EndpointTestResult>, onPassed?: () => void) => {
      const id = ++runId.current;
      const start = Date.now();
      startedAtRef.current = start;
      setStartedAt(start);
      setResult(null);
      let outcome: EndpointTestResult;
      try {
        outcome = await call();
      } catch (err) {
        // A call that throws is just another failed test, never a stuck "waiting".
        outcome = {
          success: false,
          error: err instanceof Error ? err.message : String(err),
        };
      }
      if (id !== runId.current) return;
      startedAtRef.current = null;
      setStartedAt(null);
      setLastDurationMs(Date.now() - start);
      setResult(outcome);
      if (outcome.success) onPassed?.();
    },
    []
  );

  /** Stops waiting; the call itself may still finish on the server, unseen. */
  const cancel = useCallback(() => {
    const start = startedAtRef.current;
    if (start === null) return;
    runId.current += 1;
    startedAtRef.current = null;
    setStartedAt(null);
    setLastDurationMs(Date.now() - start);
  }, []);

  /** Drops the result and any run in flight, e.g. once the setup it tested changed. */
  const reset = useCallback(() => {
    runId.current += 1;
    startedAtRef.current = null;
    setStartedAt(null);
    setResult(null);
  }, []);

  return {
    result,
    isTesting: startedAt !== null,
    startedAt,
    isSlow: lastDurationMs !== null && lastDurationMs > SLOW_API_MS,
    run,
    cancel,
    reset,
  };
}

'use client';

import { useCallback, useEffect, useState } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  dedupeHistoryByTestRun,
  mapTestResultToHistoryRow,
  TestExecutionHistoryRow,
} from './test-execution-history';

const MAX_RESULTS = 100;

interface UseTestExecutionHistoryOptions {
  testId: string | undefined;
  enabled?: boolean;
}

interface UseTestExecutionHistoryResult {
  rows: TestExecutionHistoryRow[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useTestExecutionHistory({
  testId,
  enabled = true,
}: UseTestExecutionHistoryOptions): UseTestExecutionHistoryResult {
  const [rows, setRows] = useState<TestExecutionHistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  const refetch = useCallback(() => {
    setFetchKey(key => key + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    if (!testId) {
      setError('No test ID available');
      setRows([]);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function fetchHistory() {
      try {
        setLoading(true);
        const clientFactory = new ApiClientFactory();
        const testResultsClient = clientFactory.getTestResultsClient();

        const results = await testResultsClient.getTestResults({
          filter: `test_id eq '${testId}'`,
          limit: MAX_RESULTS,
          skip: 0,
          sort_by: 'created_at',
          sort_order: 'desc',
        });

        if (cancelled) return;

        const testRunNamesMap = new Map<string, string>();
        for (const result of results.data) {
          if (result.test_run_id && result.test_run?.name) {
            testRunNamesMap.set(result.test_run_id, result.test_run.name);
          }
        }

        const missingTestRunIds = [
          ...new Set(
            results.data
              .filter(
                (r): r is typeof r & { test_run_id: string } =>
                  !!r.test_run_id && !testRunNamesMap.has(r.test_run_id)
              )
              .map(r => r.test_run_id)
          ),
        ];

        if (missingTestRunIds.length > 0) {
          const testRunsClient = clientFactory.getTestRunsClient();
          const testRunsData = await Promise.allSettled(
            missingTestRunIds.map(id => testRunsClient.getTestRun(id))
          );

          if (cancelled) return;

          testRunsData.forEach((result, index) => {
            if (result.status === 'fulfilled') {
              const testRun = result.value;
              testRunNamesMap.set(
                testRun.id,
                testRun.name || missingTestRunIds[index]
              );
            } else {
              testRunNamesMap.set(
                missingTestRunIds[index],
                missingTestRunIds[index]
              );
            }
          });
        }

        const historicalData = results.data.map(result =>
          mapTestResultToHistoryRow(result, testRunNamesMap)
        );

        setRows(dedupeHistoryByTestRun(historicalData));
        setError(null);
      } catch {
        if (!cancelled) {
          setError('Failed to load execution history');
          setRows([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchHistory();

    return () => {
      cancelled = true;
    };
  }, [testId, enabled, fetchKey]);

  return { rows, loading, error, refetch };
}

'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PassFailStats } from '@/utils/api-client/interfaces/test-results';
import {
  InsightsFilters,
  resolveInsightsTimeRange,
  timeRangeToStatsParams,
} from '../types';
import {
  BehaviorInsightColumn,
  buildBehaviorColumns,
  rowToPassFailStats,
} from '../utils/behavior-insights-utils';
import {
  fetchInsightsFailedTestIds,
  fetchInsightsQueryTestRunIds,
  insightsOverallFailedScope,
} from '@/hooks/useInsightsFailedTestIds';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

const EMPTY_SUMMARY: PassFailStats = {
  total: 0,
  passed: 0,
  failed: 0,
  pass_rate: 0,
};

export interface BehaviorInsightsData {
  summary: PassFailStats | null;
  columns: BehaviorInsightColumn[];
  /** Unique failed test case count; null while resolving or after filter change. */
  failedTestCaseCount: number | null;
  loading: boolean;
  error: string | null;
  noRuns: boolean;
}

export function useBehaviorInsightsData(
  filters: InsightsFilters,
  enabled = true
): BehaviorInsightsData {
  const [summary, setSummary] = useState<PassFailStats | null>(null);
  const [columns, setColumns] = useState<BehaviorInsightColumn[]>([]);
  const [failedTestCaseCount, setFailedTestCaseCount] = useState<number | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noRuns, setNoRuns] = useState(false);
  const { status } = useSession();
  const queryClient = useQueryClient();
  const requestIdRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isCurrentRequest = (requestId: number) =>
    requestIdRef.current === requestId;

  useEffect(() => {
    // `enabled` is the caller's capability gate (e.g. the Insights page passes
    // `test_result:read`). When denied we must not fire any request — the hook
    // still runs unconditionally (rules of hooks), so this is the direct guard
    // rather than relying on `endpointId` never being populated.
    if (!enabled || !isAuthenticated(status) || !filters.endpointId) {
      setLoading(false);
      setSummary(null);
      setColumns([]);
      setFailedTestCaseCount(0);
      setNoRuns(false);
      setError(null);
      return;
    }

    const requestId = ++requestIdRef.current;
    setLoading(true);
    setFailedTestCaseCount(null);
    setError(null);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      void (async () => {
        try {
          const runContext = {
            endpointId: filters.endpointId,
            runFilterMode: filters.runFilterMode,
            timeRange: resolveInsightsTimeRange(filters.timeRange),
            testRunIds: filters.testRunIds,
          };
          const testRunIds = await fetchInsightsQueryTestRunIds(
            queryClient,
            runContext
          );

          if (!isCurrentRequest(requestId)) return;

          if (testRunIds.length === 0) {
            setSummary(EMPTY_SUMMARY);
            setColumns([]);
            setFailedTestCaseCount(0);
            setNoRuns(true);
            setLoading(false);
            return;
          }

          setNoRuns(false);

          const insightsClient = new ApiClientFactory().getInsightsClient();

          const timeParams =
            filters.runFilterMode === 'timeRange'
              ? timeRangeToStatsParams(runContext.timeRange)
              : {};
          const measures = ['passed', 'failed', 'pass_rate'];
          const baseQuery = {
            filters: { test_run_ids: testRunIds },
            ...timeParams,
          };

          const batch = await insightsClient.getInsightsBatch({
            queries: {
              summary: {
                entity: 'test_result',
                group_by: [],
                measures,
                ...baseQuery,
              },
              behaviors: {
                entity: 'test_result',
                group_by: ['behavior_id', 'behavior'],
                measures,
                ...baseQuery,
              },
              topics: {
                entity: 'test_result',
                group_by: ['behavior_id', 'topic'],
                measures,
                ...baseQuery,
              },
              metrics: {
                entity: 'metric',
                group_by: ['behavior_id', 'metric_name'],
                measures,
                ...baseQuery,
              },
            },
          });

          if (!isCurrentRequest(requestId)) return;

          const summaryRow = batch.results.summary.rows[0];
          const overallSummary = summaryRow
            ? rowToPassFailStats(summaryRow)
            : EMPTY_SUMMARY;
          setSummary(overallSummary);
          setColumns(
            buildBehaviorColumns(
              batch.results.behaviors.rows,
              batch.results.topics.rows,
              batch.results.metrics.rows
            )
          );

          setLoading(false);

          if ((overallSummary.failed ?? 0) > 0) {
            void (async () => {
              try {
                const failedIds = await fetchInsightsFailedTestIds(
                  queryClient,
                  insightsOverallFailedScope(runContext)
                );
                if (!isCurrentRequest(requestId)) return;
                setFailedTestCaseCount(failedIds.length);
              } catch {
                if (!isCurrentRequest(requestId)) return;
                setFailedTestCaseCount(0);
              }
            })();
          } else {
            setFailedTestCaseCount(0);
          }
        } catch (err) {
          if (!isCurrentRequest(requestId)) return;
          setError(
            err instanceof Error ? err.message : 'Failed to load insights'
          );
          setLoading(false);
        }
      })();
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [
    enabled,
    status,
    queryClient,
    filters.endpointId,
    filters.runFilterMode,
    filters.timeRange,
    filters.testRunIds,
  ]);

  return {
    summary,
    columns,
    failedTestCaseCount,
    loading,
    error,
    noRuns,
  };
}

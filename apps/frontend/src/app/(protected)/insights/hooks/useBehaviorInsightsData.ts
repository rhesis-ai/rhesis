'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  PassFailStats,
  TestResultsStatsMetadata,
} from '@/utils/api-client/interfaces/test-results';
import {
  InsightsFilters,
  resolveInsightsTimeRange,
  timeRangeToStatsParams,
} from '../types';
import {
  BehaviorInsightColumn,
  buildBehaviorColumns,
  fetchTestRunIdsForEndpoint,
} from '../utils/behavior-insights-utils';
import { fetchFailedTestIdsForInsights } from '../utils/insights-failed-tests';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

const EMPTY_SUMMARY: PassFailStats = {
  total: 0,
  passed: 0,
  failed: 0,
  pass_rate: 0,
};

export interface BehaviorInsightsData {
  summary: PassFailStats | null;
  metadata: TestResultsStatsMetadata | null;
  columns: BehaviorInsightColumn[];
  /** Unique failed test case count; null while resolving or after filter change. */
  failedTestCaseCount: number | null;
  loading: boolean;
  error: string | null;
  noRuns: boolean;
}

export function useBehaviorInsightsData(
  sessionToken: string,
  filters: InsightsFilters,
  enabled = true
): BehaviorInsightsData {
  const [summary, setSummary] = useState<PassFailStats | null>(null);
  const [metadata, setMetadata] = useState<TestResultsStatsMetadata | null>(
    null
  );
  const [columns, setColumns] = useState<BehaviorInsightColumn[]>([]);
  const [failedTestCaseCount, setFailedTestCaseCount] = useState<number | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noRuns, setNoRuns] = useState(false);
  const { status } = useSession();
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
      setMetadata(null);
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
          const testRunIds = await fetchTestRunIdsForEndpoint(
            sessionToken,
            filters.endpointId,
            resolveInsightsTimeRange(filters.timeRange)
          );

          if (!isCurrentRequest(requestId)) return;

          if (testRunIds.length === 0) {
            setSummary(EMPTY_SUMMARY);
            setMetadata(null);
            setColumns([]);
            setFailedTestCaseCount(0);
            setNoRuns(true);
            setLoading(false);
            return;
          }

          setNoRuns(false);

          const factory = new ApiClientFactory(sessionToken);
          const testResultsClient = factory.getTestResultsClient();
          const behaviorClient = factory.getBehaviorClient();

          const statsParams = {
            ...timeRangeToStatsParams(
              resolveInsightsTimeRange(filters.timeRange)
            ),
            test_run_ids: testRunIds,
          };

          const [summaryResult, behaviorResult, behaviors] = await Promise.all([
            testResultsClient.getComprehensiveTestResultsStats({
              ...statsParams,
              mode: 'summary',
            }),
            testResultsClient.getComprehensiveTestResultsStats({
              ...statsParams,
              mode: 'behavior',
            }),
            behaviorClient.getBehaviors({
              limit: 100,
              sort_by: 'name',
              sort_order: 'asc',
            }),
          ]);

          if (!isCurrentRequest(requestId)) return;

          const behaviorPassRates = behaviorResult.behavior_pass_rates ?? {};
          const behaviorsWithData = behaviors.filter(
            b => behaviorPassRates[b.name] !== undefined
          );

          let perBehaviorResults: Awaited<
            ReturnType<
              typeof testResultsClient.getComprehensiveTestResultsStats
            >
          >[] = [];

          if (behaviorsWithData.length > 0) {
            perBehaviorResults = await Promise.all(
              behaviorsWithData.map(b =>
                testResultsClient.getComprehensiveTestResultsStats({
                  ...statsParams,
                  mode: 'all',
                  behavior_ids: [b.id],
                })
              )
            );
          }

          if (!isCurrentRequest(requestId)) return;

          const overallSummary =
            summaryResult.overall_pass_rates ?? EMPTY_SUMMARY;
          setSummary(overallSummary);
          setMetadata(
            summaryResult.metadata ?? behaviorResult.metadata ?? null
          );
          setColumns(
            buildBehaviorColumns(
              behaviorsWithData.map(b => ({ id: b.id, name: b.name })),
              behaviorPassRates,
              perBehaviorResults
            )
          );

          setLoading(false);

          if ((overallSummary.failed ?? 0) > 0) {
            void (async () => {
              try {
                const failedIds = await fetchFailedTestIdsForInsights(
                  sessionToken,
                  {
                    endpointId: filters.endpointId,
                    timeRange: resolveInsightsTimeRange(filters.timeRange),
                    testRunIds,
                  }
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
  }, [enabled, status, sessionToken, filters.endpointId, filters.timeRange]);

  return {
    summary,
    metadata,
    columns,
    failedTestCaseCount,
    loading,
    error,
    noRuns,
  };
}

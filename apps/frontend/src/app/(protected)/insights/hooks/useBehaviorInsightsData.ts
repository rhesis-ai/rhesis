'use client';

import { useEffect, useRef, useState } from 'react';
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
  loading: boolean;
  error: string | null;
  noRuns: boolean;
}

export function useBehaviorInsightsData(
  sessionToken: string,
  filters: InsightsFilters
): BehaviorInsightsData {
  const [summary, setSummary] = useState<PassFailStats | null>(null);
  const [metadata, setMetadata] = useState<TestResultsStatsMetadata | null>(
    null
  );
  const [columns, setColumns] = useState<BehaviorInsightColumn[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noRuns, setNoRuns] = useState(false);
  const requestIdRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isCurrentRequest = (requestId: number) =>
    requestIdRef.current === requestId;

  useEffect(() => {
    if (!sessionToken || !filters.endpointId) {
      setLoading(false);
      setSummary(null);
      setMetadata(null);
      setColumns([]);
      setNoRuns(false);
      setError(null);
      return;
    }

    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      void (async () => {
        try {
          const testRunIds = await fetchTestRunIdsForEndpoint(
            sessionToken,
            filters.endpointId
          );

          if (!isCurrentRequest(requestId)) return;

          if (testRunIds.length === 0) {
            setSummary(EMPTY_SUMMARY);
            setMetadata(null);
            setColumns([]);
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

          setSummary(summaryResult.overall_pass_rates ?? EMPTY_SUMMARY);
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
  }, [sessionToken, filters.endpointId, filters.timeRange]);

  return { summary, metadata, columns, loading, error, noRuns };
}

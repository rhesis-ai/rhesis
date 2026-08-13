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
  RequirementInsightColumn,
  RequirementOption,
  buildRequirementColumns,
  buildRequirementOptions,
  rowToPassFailStats,
} from '../utils/requirement-insights-utils';
import { fetchInsightsQueryTestRunIds } from '@/hooks/useInsightsFailedTestIds';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

const EMPTY_SUMMARY: PassFailStats = {
  total: 0,
  passed: 0,
  failed: 0,
  pass_rate: 0,
};

export interface RequirementInsightsData {
  summary: PassFailStats | null;
  columns: RequirementInsightColumn[];
  /** Full, unfiltered requirement list -- for the filter drawer's checkbox options. */
  requirementOptions: RequirementOption[];
  loading: boolean;
  error: string | null;
  noRuns: boolean;
}

export function useRequirementInsightsData(
  filters: InsightsFilters,
  enabled = true
): RequirementInsightsData {
  const [summary, setSummary] = useState<PassFailStats | null>(null);
  const [columns, setColumns] = useState<RequirementInsightColumn[]>([]);
  const [requirementOptions, setRequirementOptions] = useState<RequirementOption[]>([]);
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
      setRequirementOptions([]);
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
            setRequirementOptions([]);
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

          // `null` means "no filter" (default); `[]` means the user
          // explicitly unchecked every box -- a real, distinct state that
          // should show zero data, not silently fall back to "all". The
          // backend can't express "match zero" through an omitted filter
          // (an empty list is dropped and treated as "no restriction"), so
          // that case is handled client-side below instead of being sent
          // as a query param.
          const showsNoData =
            (filters.requirementIds !== null &&
              filters.requirementIds.length === 0) ||
            (filters.statusIds !== null && filters.statusIds.length === 0);

          // Status narrows every test_result query, including the "options"
          // scope below -- unlike requirementIds, this isn't a client-side
          // column toggle, so the checkbox list itself should only offer
          // requirements that exist within the selected status.
          const testResultFilterExtras: Record<string, string[]> = {};
          if (filters.statusIds !== null && filters.statusIds.length > 0) {
            testResultFilterExtras.status_ids = filters.statusIds;
          }

          // Unfiltered by requirementIds -- used only to populate the drawer's
          // full requirement checkbox list (with counts), independent of which
          // requirements are currently checked.
          const optionsQuery = {
            filters: { test_run_ids: testRunIds, ...testResultFilterExtras },
            ...timeParams,
          };

          // Actual display/summary scope for the test_result entity -- also
          // narrowed to the checked requirements so the pass rate and columns
          // reflect the filter, not just which columns are shown.
          const testResultQuery = {
            filters: {
              ...optionsQuery.filters,
              ...(filters.requirementIds !== null && filters.requirementIds.length > 0
                ? { requirement_ids: filters.requirementIds }
                : {}),
            },
            ...timeParams,
          };

          // The `metric` entity's registry filters don't include
          // topic_ids/status_ids (see services/insights/registry.py) --
          // sending them would 400.
          const metricQuery = {
            filters: {
              test_run_ids: testRunIds,
              ...(filters.requirementIds !== null && filters.requirementIds.length > 0
                ? { requirement_ids: filters.requirementIds }
                : {}),
            },
            ...timeParams,
          };

          const results = await insightsClient.getInsightsQuery({
            summary: {
              entity: 'test_result',
              group_by: [],
              measures,
              ...testResultQuery,
            },
            requirements: {
              entity: 'test_result',
              group_by: ['requirement_id', 'requirement'],
              measures,
              ...testResultQuery,
            },
            topics: {
              entity: 'test_result',
              group_by: ['requirement_id', 'topic_id', 'topic'],
              measures,
              ...testResultQuery,
            },
            metrics: {
              entity: 'metric',
              group_by: ['requirement_id', 'metric_name'],
              measures,
              ...metricQuery,
            },
            allRequirements: {
              entity: 'test_result',
              group_by: ['requirement_id', 'requirement'],
              measures,
              ...optionsQuery,
            },
          });

          if (!isCurrentRequest(requestId)) return;

          if (showsNoData) {
            setSummary(EMPTY_SUMMARY);
            setColumns([]);
          } else {
            const summaryRow = results.summary.rows[0];
            setSummary(
              summaryRow ? rowToPassFailStats(summaryRow) : EMPTY_SUMMARY
            );
            setColumns(
              buildRequirementColumns(
                results.requirements.rows,
                results.topics.rows,
                results.metrics.rows
              )
            );
          }
          setRequirementOptions(buildRequirementOptions(results.allRequirements.rows));

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
  }, [
    enabled,
    status,
    queryClient,
    filters.endpointId,
    filters.runFilterMode,
    filters.timeRange,
    filters.testRunIds,
    filters.requirementIds,
    filters.statusIds,
  ]);

  return {
    summary,
    columns,
    requirementOptions,
    loading,
    error,
    noRuns,
  };
}

'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { PassFailStats } from '@/utils/api-client/interfaces/test-results';
import { InsightsFilters, resolveInsightsTimeRange } from '../types';
import {
  RequirementInsightColumn,
  RequirementInsightsResult,
  RequirementOption,
  fetchRequirementInsights,
} from '../utils/requirement-insights-utils';
import { fetchInsightsQueryTestRunIds } from '@/hooks/useInsightsFailedTestIds';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

export interface RequirementInsightsData {
  summary: PassFailStats | null;
  columns: RequirementInsightColumn[];
  /** Full, unfiltered requirement list -- for the filter drawer's checkbox options. */
  requirementOptions: RequirementOption[];
  loading: boolean;
  error: string | null;
  noRuns: boolean;
}

/** Server-prefetched result, valid only for the exact `filters` it was fetched with. */
export interface RequirementInsightsSeed {
  filters: InsightsFilters;
  data: RequirementInsightsResult;
}

/** The subset of filter fields that changes what gets fetched. */
function fetchKey(filters: InsightsFilters): string {
  return JSON.stringify([
    filters.endpointId,
    filters.runFilterMode,
    resolveInsightsTimeRange(filters.timeRange),
    filters.testRunIds,
    filters.requirementIds,
    filters.statusIds,
  ]);
}

export function useRequirementInsightsData(
  filters: InsightsFilters,
  enabled = true,
  seed?: RequirementInsightsSeed
): RequirementInsightsData {
  // The seed only applies to the filters it was fetched for; anything else
  // starts empty and fetches as before.
  const seeded =
    seed !== undefined && fetchKey(seed.filters) === fetchKey(filters);
  const [summary, setSummary] = useState<PassFailStats | null>(
    seeded ? seed.data.summary : null
  );
  const [columns, setColumns] = useState<RequirementInsightColumn[]>(
    seeded ? seed.data.columns : []
  );
  const [requirementOptions, setRequirementOptions] = useState<
    RequirementOption[]
  >(seeded ? seed.data.requirementOptions : []);
  const [loading, setLoading] = useState(!seeded);
  const [error, setError] = useState<string | null>(null);
  const [noRuns, setNoRuns] = useState(seeded ? seed.data.noRuns : false);
  const { status } = useSession();
  const queryClient = useQueryClient();
  const requestIdRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Skips the fetch while the filters still match what the server fetched.
  const seedKeyRef = useRef<string | null>(seeded ? fetchKey(filters) : null);

  const isCurrentRequest = (requestId: number) =>
    requestIdRef.current === requestId;

  useEffect(() => {
    // `enabled` is the caller's capability gate (e.g. the Insights page passes
    // `test_result:read`). When denied we must not fire any request — the hook
    // still runs unconditionally (rules of hooks), so this is the direct guard
    // rather than relying on `endpointId` never being populated.
    if (!enabled || !isAuthenticated(status) || !filters.endpointId) {
      seedKeyRef.current = null;
      setLoading(false);
      setSummary(null);
      setColumns([]);
      setRequirementOptions([]);
      setNoRuns(false);
      setError(null);
      return;
    }

    // Keyed (not a one-shot flag) so Strict Mode's double effect run doesn't
    // refetch; the first filter change drops it for good.
    if (seedKeyRef.current !== null) {
      if (seedKeyRef.current === fetchKey(filters)) return;
      seedKeyRef.current = null;
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
          const testRunIds = await fetchInsightsQueryTestRunIds(queryClient, {
            endpointId: filters.endpointId,
            runFilterMode: filters.runFilterMode,
            timeRange: resolveInsightsTimeRange(filters.timeRange),
            testRunIds: filters.testRunIds,
          });

          if (!isCurrentRequest(requestId)) return;

          const result = await fetchRequirementInsights(filters, testRunIds);

          if (!isCurrentRequest(requestId)) return;

          setSummary(result.summary);
          setColumns(result.columns);
          setRequirementOptions(result.requirementOptions);
          setNoRuns(result.noRuns);
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
    // `filters` is read field-by-field so a new object with equal fields
    // doesn't refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

'use client';

import * as React from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { metricTargetKeys, spanAttributeKeys } from '@/constants/query-keys';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  MetricTarget,
  MetricTargetPreview,
} from '@/utils/api-client/interfaces/metric';
import type { SpanAttributeCatalogue } from '@/utils/api-client/interfaces/telemetry';

/** How long the builder waits after the last edit before it previews. */
export const TARGET_PREVIEW_DEBOUNCE_MS = 600;
/** The latest traces a preview reads. */
export const TARGET_PREVIEW_TRACES = 50;
/** Days of spans the attribute catalogue reads. */
export const ATTRIBUTE_CATALOGUE_DAYS = 7;

const CATALOGUE_STALE_MS = 5 * 60_000;

/** The attribute keys a project's recent spans carry, by span kind. */
export function useSpanAttributeCatalogue(projectId: string | null) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<SpanAttributeCatalogue>({
    queryKey: spanAttributeKeys.catalogue(projectId ?? ''),
    queryFn: () =>
      new ApiClientFactory().getTelemetryClient().getAttributeCatalogue({
        project_id: projectId ?? '',
        days: ATTRIBUTE_CATALOGUE_DAYS,
      }),
    enabled: isAuthenticated && !!projectId,
    staleTime: CATALOGUE_STALE_MS,
    retry: false,
  });
}

/** *value*, once it has stopped changing for *delay* ms. */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/**
 * What *target* picks in the project's latest traces, re-read a moment after
 * the last edit. Null *target* (an incomplete draft) previews nothing.
 */
export function useMetricTargetPreview(
  projectId: string | null,
  target: MetricTarget | null
) {
  const isAuthenticated = useIsAuthenticated();
  const key = target ? JSON.stringify(target) : '';
  const debouncedKey = useDebouncedValue(key, TARGET_PREVIEW_DEBOUNCE_MS);
  const query = useQuery<MetricTargetPreview, Error>({
    queryKey: metricTargetKeys.preview(projectId ?? '', debouncedKey),
    queryFn: ({ signal }) =>
      new ApiClientFactory().getMetricsClient().previewMetricTarget(
        {
          project_id: projectId ?? '',
          target: JSON.parse(debouncedKey) as MetricTarget,
          traces: TARGET_PREVIEW_TRACES,
        },
        signal
      ),
    enabled: isAuthenticated && !!projectId && !!debouncedKey,
    // Keep the last counts on screen while the next edit's preview loads.
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: 30_000,
  });
  return { ...query, pending: key !== debouncedKey };
}

'use client';

import * as React from 'react';
import type { UUID } from 'crypto';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import { useQuery } from '@tanstack/react-query';
import { metricKeys } from '@/constants/query-keys';
import { useMetricTargets } from '@/hooks/useLookups';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  MetricDetail,
  MetricTarget,
} from '@/utils/api-client/interfaces/metric';
import {
  formatMetricTarget,
  getMetricTarget,
  getMetricTargetIcon,
} from '@/utils/metric-targets';
import { targetKey } from '@/utils/metric-target-draft';
import TargetSummaryText from '@/app/(protected)/metrics/components/TargetSummaryText';

interface TargetFilterChipProps {
  /** The metric whose target link opened the page, if any. */
  metricId?: string | null;
  /** The target the list is filtered to, as JSON; unset for old links. */
  target?: string;
  /** Called when the chip is removed; the page drops the target filter. */
  onRemove: () => void;
  /**
   * An old link names the metric but not its target (it filtered by tool and
   * span type instead): called with the metric's target, so the list filters
   * exactly what the chip names.
   */
  onTargetLoaded?: (target: string) => void;
}

function parsedTarget(json: string | undefined): MetricTarget | null {
  if (!json) return null;
  try {
    return JSON.parse(json) as MetricTarget;
  } catch {
    return null;
  }
}

/**
 * Says which target the spans are filtered to ("Target: each tool call named
 * issue_refund · from Correct refund arguments"). The words are the metric's
 * `target_summary_short` from the API; a target with no metric behind it shows
 * its preset's label. Every target filters exactly, so nothing is left unapplied.
 */
export default function TargetFilterChip({
  metricId,
  target: targetJson,
  onRemove,
  onTargetLoaded,
}: TargetFilterChipProps) {
  const isAuthenticated = useIsAuthenticated();
  const { data: choices } = useMetricTargets();
  const { data: metric } = useQuery<MetricDetail>({
    queryKey: metricKeys.detail(metricId ?? ''),
    queryFn: () =>
      new ApiClientFactory().getMetricsClient().getMetric(metricId as UUID),
    enabled: isAuthenticated && !!metricId,
    retry: false,
  });

  const urlTarget = parsedTarget(targetJson);
  const metricTarget = metric ? getMetricTarget(metric) : null;
  const target = urlTarget ?? metricTarget;

  React.useEffect(() => {
    if (!targetJson && metricTarget) {
      onTargetLoaded?.(JSON.stringify(metricTarget));
    }
  }, [targetJson, metricTarget, onTargetLoaded]);

  if (!target) return null;

  // The metric's words only describe the filter while its target is the one applied.
  const sameTarget =
    !urlTarget ||
    (!!metricTarget && targetKey(metricTarget) === targetKey(urlTarget));
  const summary = sameTarget ? metric?.target_summary_short : null;
  if (!summary && !choices) return null;

  return (
    <Box
      sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', alignItems: 'center' }}
    >
      <Chip
        data-testid="target-filter-chip"
        color="primary"
        variant="outlined"
        icon={getMetricTargetIcon(target.on, choices, 'small', target.where)}
        label={
          <>
            Target:{' '}
            {summary ? (
              <TargetSummaryText summary={summary} />
            ) : (
              formatMetricTarget(target, choices)
            )}
            {metric?.name && sameTarget ? ` · from ${metric.name}` : null}
          </>
        }
        onDelete={onRemove}
        sx={{ maxWidth: '100%' }}
      />
    </Box>
  );
}

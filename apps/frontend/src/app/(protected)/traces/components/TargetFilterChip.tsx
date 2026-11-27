'use client';

import * as React from 'react';
import type { UUID } from 'crypto';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
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
  isTargetShape,
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
  /**
   * Set in the traces view, where the target doesn't filter (the traces list
   * takes no target): the chip says so and offers the spans view.
   */
  onShowSpans?: () => void;
}

function parsedTarget(json: string | undefined): MetricTarget | null {
  if (!json) return null;
  try {
    const parsed: unknown = JSON.parse(json);
    return isTargetShape(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * Says which target the spans are filtered to ("Target: each tool call named
 * issue_refund · from Correct refund arguments"). The words are the metric's
 * `target_summary_short` from the API; a target with no metric behind it shows
 * its preset's label. It filters the spans view exactly; the traces list takes
 * no target, so there the chip says it applies to spans.
 */
export default function TargetFilterChip({
  metricId,
  target: targetJson,
  onRemove,
  onTargetLoaded,
  onShowSpans,
}: TargetFilterChipProps) {
  const noteId = React.useId();
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

  const inactive = !!onShowSpans;

  return (
    <Box
      sx={{
        mb: 2,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        columnGap: 1.5,
        rowGap: 0.5,
      }}
    >
      <Chip
        data-testid="target-filter-chip"
        color={inactive ? 'default' : 'primary'}
        variant="outlined"
        aria-describedby={inactive ? noteId : undefined}
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
      {inactive && (
        <>
          <Typography
            id={noteId}
            variant="body2"
            color="text.secondary"
            data-testid="target-filter-inactive"
          >
            Applies to the spans view.
          </Typography>
          <Button size="small" onClick={onShowSpans}>
            Show spans
          </Button>
        </>
      )}
    </Box>
  );
}

'use client';

import * as React from 'react';
import type { UUID } from 'crypto';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { metricKeys } from '@/constants/query-keys';
import { useMetricTargets } from '@/hooks/useLookups';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import {
  getMetricTarget,
  getMetricTargetIcon,
  targetPhrase,
} from '@/utils/metric-targets';
import { targetTraceFilters, unappliedRefinements } from './target-filters';
import type { TraceDrawerFilters } from './trace-filter-params';

interface TargetFilterChipProps {
  metricId: string;
  /** Called with the filters the target set, which the page removes. */
  onRemove: (applied: Partial<TraceDrawerFilters>) => void;
}

/**
 * Says which metric's target the list is filtered to ("Target: each tool call
 * named issue_refund · from Correct refund arguments"), when the page was opened
 * from a metric's target link. Removing it clears the filters the target set.
 */
export default function TargetFilterChip({
  metricId,
  onRemove,
}: TargetFilterChipProps) {
  const isAuthenticated = useIsAuthenticated();
  const { data: choices } = useMetricTargets();
  const { data: metric } = useQuery<MetricDetail>({
    queryKey: metricKeys.detail(metricId),
    queryFn: () =>
      new ApiClientFactory().getMetricsClient().getMetric(metricId as UUID),
    enabled: isAuthenticated && !!metricId,
    retry: false,
  });

  const target = metric ? getMetricTarget(metric) : null;
  const phrase = target ? targetPhrase(target, choices) : null;
  if (!target || !phrase) return null;

  const label = [
    `Target: ${phrase}${target.name ? ` named ${target.name}` : ''}`,
    metric?.name ? `from ${metric.name}` : null,
  ]
    .filter(Boolean)
    .join(' · ');
  const unapplied = unappliedRefinements(target);

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
        color="primary"
        variant="outlined"
        icon={getMetricTargetIcon(target.on, choices)}
        label={label}
        onDelete={() => onRemove(targetTraceFilters(target, choices).filters)}
        sx={{ maxWidth: '100%' }}
      />
      {unapplied.length > 0 && (
        <Typography
          variant="body2"
          color="text.secondary"
          data-testid="target-filter-unapplied"
        >
          Not applied here: {unapplied.join(', ')}
        </Typography>
      )}
    </Box>
  );
}

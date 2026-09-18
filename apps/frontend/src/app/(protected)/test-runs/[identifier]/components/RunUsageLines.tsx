'use client';

import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import ModelLabel from '@/components/common/ModelLabel';
import { formatCost, formatTokenCount, isCostKnown } from '@/utils/trace-utils';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

/** Matches the "Pass rate: 82%" line the comparison cards already use. */
function StatLine({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Typography variant="body2" color="text.secondary">
      {label}:{' '}
      <Box component="span" sx={{ fontWeight: 700, color: 'text.primary' }}>
        {children}
      </Box>
    </Typography>
  );
}

/**
 * How much more or less of something this run used than the baseline.
 *
 * Coloured the opposite way round from the pass-rate delta beside it: for both
 * spend and tokens, less is the improvement.
 */
function Delta({
  current,
  baseline,
  format,
}: {
  current: number;
  baseline: number;
  format: (value: number) => string;
}) {
  const theme = useTheme();
  // Rounded to the six places the backend already rounds costs to, and to the
  // most formatCost will ever print. Subtracting two equal-looking floats
  // leaves noise around 1e-17, which is not zero and renders as "$0.000000" --
  // a delta claiming a difference too small to write down.
  const delta = Number((current - baseline).toFixed(6));
  if (delta === 0) return null;

  return (
    <Box
      component="span"
      sx={{
        ml: 0.5,
        fontWeight: 700,
        color:
          delta < 0 ? theme.palette.success.main : theme.palette.error.main,
      }}
    >
      ({delta > 0 ? '+' : '−'}
      {format(Math.abs(delta))})
    </Box>
  );
}

/**
 * What a run in the comparison spent, beneath its pass rate.
 *
 * Both cards read the same endpoint through the same hook, so the baseline and
 * the current run cannot describe the same figure differently, and neither can
 * disagree with the Usage card on the run's own summary.
 *
 * Renders nothing at all until the numbers arrive. A comparison is about the
 * difference between two runs, and half a comparison invites the reader to
 * infer one.
 */
export default function RunUsageLines({
  usage,
  compareTo,
}: {
  usage: TraceMetricsResponse | null;
  /** The other run's usage, when this is the side that shows the delta. */
  compareTo?: TraceMetricsResponse | null;
}) {
  if (!usage || usage.total_traces === 0) return null;

  const costKnown = isCostKnown(usage);
  const models = usage.models_used ?? [];
  // Tokens come off the spans, so a run with traces always has them. Cost has
  // to be priced on both sides before a difference means anything.
  const comparable = compareTo != null && compareTo.total_traces > 0;
  const canCompareCost = comparable && costKnown && isCostKnown(compareTo);

  return (
    <>
      <StatLine label="Cost">
        {costKnown ? formatCost(usage.total_cost_usd) : '—'}
        {canCompareCost && (
          <Delta
            current={usage.total_cost_usd}
            baseline={compareTo.total_cost_usd}
            format={formatCost}
          />
        )}
      </StatLine>
      <StatLine label="Tokens">
        {formatTokenCount(usage.total_tokens)}
        {comparable && (
          <Delta
            current={usage.total_tokens}
            baseline={compareTo.total_tokens}
            format={formatTokenCount}
          />
        )}
      </StatLine>
      {models.length > 0 && (
        <StatLine label="Model">
          <ModelLabel
            component="span"
            truncate={false}
            models={models}
            providers={usage.providers_used}
            sx={{ fontWeight: 'inherit', color: 'inherit' }}
          />
        </StatLine>
      )}
    </>
  );
}

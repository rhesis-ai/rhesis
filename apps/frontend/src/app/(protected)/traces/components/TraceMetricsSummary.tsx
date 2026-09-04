'use client';

import { useEffect, useState } from 'react';
import { Box, Grid, Typography } from '@mui/material';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import LayersIcon from '@mui/icons-material/Layers';
import PaidIcon from '@mui/icons-material/Paid';
import TokenIcon from '@mui/icons-material/Token';
import { SummaryCard } from '@/components/common/SummaryCard';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';
import { formatCost, formatTokenCount } from '@/utils/trace-utils';

interface TraceMetricsSummaryProps {
  projectId: string | null;
  environment?: string;
  startTimeAfter?: string;
  startTimeBefore?: string;
  /**
   * True when a filter the metrics endpoint cannot honor is active (endpoint,
   * trace source, evaluation status, search, ...). The tiles then cover more
   * traces than the table lists, and say so rather than appearing to disagree.
   */
  hasUnsupportedFilters?: boolean;
  /** Bumped by the refresh control, to re-fetch alongside the table. */
  refreshTrigger?: number;
}

/**
 * Project-level totals above the traces table.
 *
 * Fetched with useEffect rather than react-query: the traces page has no query
 * cache (useList/usePaginatedList are hand-rolled), so there would be no key to
 * invalidate. Mirrors how TraceDrawer fetches a single trace.
 */
export default function TraceMetricsSummary({
  projectId,
  environment,
  startTimeAfter,
  startTimeBefore,
  hasUnsupportedFilters = false,
  refreshTrigger,
}: TraceMetricsSummaryProps) {
  const [metrics, setMetrics] = useState<TraceMetricsResponse | null>(null);

  useEffect(() => {
    if (!projectId) {
      setMetrics(null);
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        const client = new ApiClientFactory(
          undefined,
          projectId
        ).getTelemetryClient();
        const result = await client.getMetrics({
          project_id: projectId,
          ...(environment ? { environment } : {}),
          ...(startTimeAfter ? { start_time_after: startTimeAfter } : {}),
          ...(startTimeBefore ? { start_time_before: startTimeBefore } : {}),
        });
        if (!cancelled) {
          setMetrics(result);
        }
      } catch {
        // The tiles are supplementary; a failure here must not take the table
        // down with it, and the table surfaces its own errors.
        if (!cancelled) {
          setMetrics(null);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [projectId, environment, startTimeAfter, startTimeBefore, refreshTrigger]);

  if (!metrics) {
    return null;
  }

  const scope = hasUnsupportedFilters
    ? 'Whole project, not narrowed by the active filters'
    : undefined;

  return (
    <Box sx={{ mb: 3 }}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Traces"
            value={metrics.total_traces.toLocaleString()}
            subtitle={scope}
            icon={<AccountTreeIcon />}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Spans"
            value={metrics.total_spans.toLocaleString()}
            subtitle={scope}
            icon={<LayersIcon />}
            color="info"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Tokens"
            value={formatTokenCount(metrics.total_tokens)}
            subtitle={scope}
            icon={<TokenIcon />}
            color="success"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Cost"
            value={formatCost(metrics.total_cost_usd)}
            subtitle={scope}
            icon={<PaidIcon />}
            color="warning"
          />
        </Grid>
      </Grid>
      {hasUnsupportedFilters && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1 }}
        >
          Totals cover the whole project for the selected environment and time
          range. The table below is narrowed further by the active filters.
        </Typography>
      )}
    </Box>
  );
}

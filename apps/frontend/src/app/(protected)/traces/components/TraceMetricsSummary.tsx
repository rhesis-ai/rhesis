'use client';

import { useEffect, useState } from 'react';
import { Box, Grid, Link, Tooltip, Typography } from '@mui/material';
import KpiCard from '../../test-runs/[identifier]/components/summary/KpiCard';
import ModelLabel from '@/components/common/ModelLabel';
import { useCurrency } from '@/contexts/CurrencyContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';
import {
  COST_TOOLTIP,
  COSTS_DOC_URL,
  formatTokenCount,
  hasTracedUsage,
  isCostKnown,
  isPricingInProgress,
  NO_COST_DATA,
  NO_COST_DATA_TOOLTIP,
  PRICING_IN_PROGRESS,
  tokenSplitLabel,
} from '@/utils/trace-utils';

interface TraceMetricsSummaryProps {
  projectId: string | null;
  /** Narrows the totals to one test run, for the Traces tab inside a run. */
  testRunId?: string;
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
  testRunId,
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
          ...(testRunId ? { test_run_id: testRunId } : {}),
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
  }, [
    projectId,
    testRunId,
    environment,
    startTimeAfter,
    startTimeBefore,
    refreshTrigger,
  ]);

  // Held back for a scope that has traced nothing: the table below says so in
  // its own empty state, and four tiles of zero say it less well.
  if (!metrics || !hasTracedUsage(metrics)) {
    return null;
  }

  const scope = hasUnsupportedFilters
    ? 'Whole project, not narrowed by the active filters'
    : undefined;

  // Busiest first, which is the order a reader wants, and stable: the endpoint
  // groups without an ORDER BY, so the keys arrive in whatever order the
  // database produced them and the hover would otherwise reshuffle itself.
  const spanTypes = Object.entries(metrics.operation_breakdown ?? {})
    .sort(
      ([aName, aCount], [bName, bCount]) =>
        bCount - aCount || aName.localeCompare(bName)
    )
    .map(([name]) => name);
  const errorSpans = metrics.error_spans;
  // From the counts rather than the rounded rate, and capped below 100 while
  // any span failed: rounding alone put "1 error · 100% ok" on screen for
  // every scope past 199 spans, a sentence that argues with itself. Capping
  // rather than flooring keeps 98.7% reading as 99 rather than 98.
  const okShare = metrics.total_spans
    ? Math.min(
        errorSpans > 0 ? 99 : 100,
        Math.round(
          ((metrics.total_spans - errorSpans) / metrics.total_spans) * 100
        )
      )
    : 100;
  const models = metrics.models_used ?? [];
  const providers = metrics.providers_used ?? [];
  const split = tokenSplitLabel(
    metrics.total_input_tokens,
    metrics.total_output_tokens
  );

  return (
    <Box sx={{ mb: 3 }}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Traces"
            value={metrics.total_traces.toLocaleString()}
            subtitle={
              spanTypes.length > 0 ? (
                <HoverList
                  label={`${spanTypes.length} ${
                    spanTypes.length === 1 ? 'span type' : 'span types'
                  }`}
                  items={spanTypes}
                />
              ) : (
                scope
              )
            }
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Spans"
            value={metrics.total_spans.toLocaleString()}
            subtitle={
              errorSpans > 0
                ? `${errorSpans.toLocaleString()} ${
                    errorSpans === 1 ? 'error' : 'errors'
                  } \u00b7 ${okShare}% ok`
                : 'No errors'
            }
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <CostTile metrics={metrics} split={split} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Models"
            value={models.length.toLocaleString()}
            valueSuffix={models.length === 1 ? 'model' : 'models'}
            // Names them rather than counting the providers too: a count of
            // providers says less than the model that produced the spend, and
            // the label carries the provider anyway as its prefix.
            subtitle={
              models.length > 0 ? (
                <ModelLabel
                  component="span"
                  truncate={false}
                  models={models}
                  providers={providers}
                />
              ) : undefined
            }
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

/** A count that names what it counted, on hover. */
function HoverList({ label, items }: { label: string; items: string[] }) {
  return (
    <Tooltip title={items.join(', ')}>
      <Box component="span" sx={{ borderBottom: '1px dotted', cursor: 'help' }}>
        {label}
      </Box>
    </Tooltip>
  );
}

/**
 * What the scope spent. Cost leads where it is known; where it is not, tokens
 * lead and the tile says which kind of silence it is -- the same rule and the
 * same words as the test run summary card, which reads its copy from the same
 * constants in trace-utils, so the two cannot describe one run differently.
 */
function CostTile({
  metrics,
  split,
}: {
  metrics: TraceMetricsResponse;
  split?: string;
}) {
  const { format: money } = useCurrency();
  const tokens = [`${formatTokenCount(metrics.total_tokens)} tokens`, split]
    .filter(Boolean)
    .join(' · ');

  if (!isCostKnown(metrics)) {
    if (isPricingInProgress(metrics)) {
      return (
        <KpiCard
          title="Cost"
          value={formatTokenCount(metrics.total_tokens)}
          valueSuffix="tokens"
          subtitle={PRICING_IN_PROGRESS}
          infoTooltip={COST_TOOLTIP}
        />
      );
    }

    return (
      <KpiCard
        title="Cost"
        value={NO_COST_DATA}
        valueVariant="h6"
        valueColor="text.secondary"
        // The token count without its input/output split: the split plus the
        // link wraps onto a third line and strands "Why?" on its own.
        subtitle={
          <>
            {formatTokenCount(metrics.total_tokens)} tokens &middot;{' '}
            <Link
              href={COSTS_DOC_URL}
              target="_blank"
              rel="noopener noreferrer"
              underline="hover"
            >
              Why?
            </Link>
          </>
        }
        infoTooltip={NO_COST_DATA_TOOLTIP}
      />
    );
  }

  return (
    <KpiCard
      title="Cost"
      value={money(metrics.total_cost_usd)}
      // One string rather than flex children: both halves are plain text, so
      // the separator can be part of the sentence and wrap with it, instead of
      // being an element whose spacing lives in CSS and is lost on copy.
      subtitle={tokens}
      infoTooltip={COST_TOOLTIP}
    />
  );
}

'use client';

import React, { useCallback, useMemo } from 'react';
import { Box, Grid, LinearProgress } from '@mui/material';
import KpiCard from './KpiCard';
import VerdictStrip from './VerdictStrip';
import { deriveRunStatus } from './run-status';
import { formatDuration } from './run-meta';
import { computeVerdictBlocks, formatVerdictBlocks } from './verdict-model';
import {
  aggregateGroupByTest,
  computeGroupRollup,
  type TestTimingMap,
} from './verdict-timeline';
import { describeStrip } from './verdict-strip-render';
import { STRIP_HEIGHTS } from './summary-tokens';
import { formatCost, formatTokenCount } from '@/utils/trace-utils';
import { useTestRunUsage } from '../../hooks/useTestRunUsage';
import type {
  VerdictMatrix,
  TestRunDetail,
} from '@/utils/api-client/interfaces/test-run';

interface KpiRowProps {
  matrix: VerdictMatrix;
  testRun: TestRunDetail;
  isRunning: boolean;
  testIds: string[];
  timings: TestTimingMap;
  onViewFailures?: () => void;
}

export default function KpiRow({
  matrix,
  testRun,
  isRunning,
  testIds,
  timings,
  onViewFailures,
}: KpiRowProps) {
  const { kpis } = matrix;
  const usage = useTestRunUsage(testRun.id);

  const durationDisplay = useMemo(() => {
    if (isRunning) return undefined;
    const { duration } = deriveRunStatus(testRun);
    return duration !== null
      ? `Ran for ${formatDuration(duration)}`
      : undefined;
  }, [testRun, isRunning]);

  // Run-wide per-test roll-up (same aggregation as a requirement group's,
  // just scoped to every row instead of one requirement's) -- this is what
  // the Pass Rate card's sparkline and "N of M tests" subtitle are built
  // from, distinct from kpis.pass_rate, which is a per-verdict rate.
  const runRollup = useMemo(
    () => aggregateGroupByTest(matrix.rows, testIds, timings, Infinity),
    [matrix.rows, testIds, timings]
  );

  const sparklineAt = useCallback(
    (t: number) => computeGroupRollup(matrix.rows, testIds, timings, t),
    [matrix.rows, testIds, timings]
  );

  const passRateStripAriaLabel = useMemo(
    () => describeStrip('Pass rate', runRollup.rollup),
    [runRollup.rollup]
  );

  const passRateDisplay =
    kpis.pass_rate !== null ? (kpis.pass_rate * 100).toFixed(1) : '--';

  const testsProgress =
    kpis.tests_total > 0 ? (kpis.tests_executed / kpis.tests_total) * 100 : 0;

  const verdictBlocksSubtitle = useMemo(() => {
    const blocks = computeVerdictBlocks(matrix.requirements, matrix.rows);
    return formatVerdictBlocks(blocks) || undefined;
  }, [matrix.requirements, matrix.rows]);

  // Failures used to be its own card; folded in here so failing runs don't
  // need two cards to tell "how many verdicts" and "how many of them failed".
  // A failure is the more urgent fact, so it takes over the card's headline
  // number when there is one -- verdicts resolved/planned drops to the
  // subtitle instead of the other way around.
  const failedMetricCount = useMemo(
    () =>
      new Set(matrix.rows.filter(r => r.failed > 0).map(r => r.metric_key))
        .size,
    [matrix.rows]
  );

  const hasFailures = kpis.failures > 0;

  const verdictsSubtitle = hasFailures
    ? `${kpis.verdicts_resolved} of ${kpis.verdicts_planned} verdicts` +
      (failedMetricCount > 0
        ? ` · ${failedMetricCount} metric${failedMetricCount === 1 ? '' : 's'} affected`
        : '')
    : verdictBlocksSubtitle;

  return (
    <Box sx={{ mb: 4 }}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Pass rate"
            value={passRateDisplay}
            valueSuffix={kpis.pass_rate !== null ? '%' : undefined}
            subtitle={
              runRollup.total > 0
                ? `${runRollup.passed} of ${runRollup.total} tests`
                : undefined
            }
            visual={
              runRollup.total > 0 ? (
                <Box sx={{ mt: 1.5 }}>
                  <VerdictStrip
                    cellsAt={sparklineAt}
                    dataVersion={matrix.version}
                    height={STRIP_HEIGHTS.shape}
                    ariaLabel={passRateStripAriaLabel}
                  />
                </Box>
              ) : undefined
            }
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Tests executed"
            value={kpis.tests_executed}
            valueSuffix={`/ ${kpis.tests_total}`}
            subtitle={durationDisplay}
            visual={
              kpis.tests_total > 0 ? (
                <LinearProgress
                  variant="determinate"
                  value={testsProgress}
                  sx={{ mt: 1.5, borderRadius: 1 }}
                />
              ) : undefined
            }
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title={hasFailures ? 'Failures' : 'Verdicts'}
            value={hasFailures ? kpis.failures : kpis.verdicts_resolved}
            valueSuffix={
              hasFailures
                ? `/ ${kpis.tests_total}`
                : `/ ${kpis.verdicts_planned}`
            }
            valueColor={hasFailures ? 'error.main' : undefined}
            subtitle={verdictsSubtitle}
            infoTooltip={
              hasFailures
                ? 'Tests with at least one failing verdict. Click to view them.'
                : 'Each test/metric pair produces one verdict. Shows verdicts resolved out of the total planned for this run.'
            }
            onClick={hasFailures ? onViewFailures : undefined}
          />
        </Grid>

        {/* Held back until the numbers arrive rather than shown as zeros, the
            same way the rollup tiles on the Traces page behave. */}
        {usage && (
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiCard
              title="Usage"
              value={formatTokenCount(usage.total_tokens)}
              valueLabel="tokens"
              secondary={{
                value: formatCost(usage.total_cost_usd),
                label: 'cost',
              }}
              subtitle={`across ${usage.total_traces} ${
                usage.total_traces === 1 ? 'trace' : 'traces'
              }`}
              infoTooltip="Tokens and cost across this run's traced LLM calls. Cost appears once enrichment has priced the run."
            />
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

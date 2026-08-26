'use client';

import React, { useMemo } from 'react';
import { Box, Grid, LinearProgress } from '@mui/material';
import KpiCard from './KpiCard';
import VerdictStrip from './VerdictStrip';
import { deriveRunStatus } from './run-status';
import { formatDuration } from './run-meta';
import {
  aggregateGroupByTest,
  computeVerdictBlocks,
  formatVerdictBlocks,
} from './verdict-model';
import { describeStrip } from './verdict-strip-render';
import { STRIP_HEIGHTS } from './summary-tokens';
import type {
  VerdictMatrix,
  TestRunDetail,
} from '@/utils/api-client/interfaces/test-run';

interface KpiRowProps {
  matrix: VerdictMatrix;
  testRun: TestRunDetail;
  isRunning: boolean;
  testIds: string[];
  generatingIds: Set<string>;
  evaluatingIds: Set<string>;
  onViewFailures?: () => void;
}

export default function KpiRow({
  matrix,
  testRun,
  isRunning,
  testIds,
  generatingIds,
  evaluatingIds,
  onViewFailures,
}: KpiRowProps) {
  const { kpis } = matrix;

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
    () =>
      aggregateGroupByTest(matrix.rows, testIds, generatingIds, evaluatingIds),
    [matrix.rows, testIds, generatingIds, evaluatingIds]
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
                    cells={runRollup.rollup}
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
            title="Verdicts"
            value={kpis.verdicts_resolved}
            valueSuffix={`/ ${kpis.verdicts_planned}`}
            subtitle={verdictBlocksSubtitle}
            infoTooltip="Each test/metric pair produces one verdict. Shows verdicts resolved out of the total planned for this run."
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Failures"
            value={kpis.failures}
            valueColor={kpis.failures > 0 ? 'error.main' : undefined}
            subtitle={
              kpis.failures > 0
                ? `across ${new Set(matrix.rows.filter(r => r.failed > 0).map(r => r.metric_key)).size} metrics`
                : undefined
            }
            onClick={kpis.failures > 0 ? onViewFailures : undefined}
          />
        </Grid>
      </Grid>
    </Box>
  );
}

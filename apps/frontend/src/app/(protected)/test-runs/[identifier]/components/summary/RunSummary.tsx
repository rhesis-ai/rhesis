'use client';

import React, { useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Box,
  CircularProgress,
  Stack,
  Typography,
  useMediaQuery,
} from '@mui/material';
import RunClockProvider from './RunClockProvider';
import KpiRow from './KpiRow';
import RequirementTable from './RequirementTable';
import BreakdownsDrawer from './BreakdownsDrawer';
import { useTestRunLive } from './hooks/useTestRunLive';
import {
  isDensityMode,
  useDensityPreference,
} from './hooks/useDensityPreference';
import { buildTimingMap, timelineDuration } from './verdict-timeline';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface RunSummaryProps {
  testRunId: string;
  testRun: TestRunDetail;
  onViewRequirement?: (id: string) => void;
  onViewMetric?: (name: string, reqId?: string) => void;
  onViewFailures?: () => void;
}

const DS_PER_SECOND = 10;

export default function RunSummary({
  testRunId,
  testRun,
  onViewRequirement,
  onViewMetric,
  onViewFailures,
}: RunSummaryProps) {
  const { matrix, isLoading, isTerminal } = useTestRunLive(testRunId);

  // A "watch it run" redirect (just launched/re-ran this test set) forces
  // Detail view for this visit via ?density=, regardless of any stored
  // preference -- see useDensityPreference's forceDensity doc.
  const searchParams = useSearchParams();
  const forceDensity = useMemo(() => {
    const raw = searchParams.get('density');
    return isDensityMode(raw) ? raw : null;
  }, [searchParams]);

  const { density, setDensity } = useDensityPreference({
    isTerminal,
    testRunId,
    forceDensity,
  });

  // Below ~720px the Numbers+shape strip is too small to read and Detail's
  // fixed name column eats the row -- force Numbers and hide the control,
  // without touching the persisted preference so it's restored on widen.
  const isNarrow = useMediaQuery('(max-width:720px)');
  const effectiveDensity = isNarrow ? 'numbers' : density;

  const testIds = useMemo(() => (matrix?.test_ids ?? []).map(String), [matrix]);

  // Per-test execution timing is what the strip animates from. Absent (an old
  // run whose cache lapsed, or one too large to animate) the map is empty and
  // every cell renders in its settled state.
  const timings = useMemo(
    () =>
      buildTimingMap(
        testIds,
        matrix?.test_started_ds ?? null,
        matrix?.test_generated_ds ?? null,
        matrix?.test_resolved_ds ?? null
      ),
    [
      testIds,
      matrix?.test_started_ds,
      matrix?.test_generated_ds,
      matrix?.test_resolved_ds,
    ]
  );

  const serverElapsed = useMemo(
    () =>
      typeof matrix?.elapsed_ds === 'number'
        ? matrix.elapsed_ds / DS_PER_SECOND
        : null,
    [matrix?.elapsed_ds]
  );

  // A finished run's length is the last moment any test reached, which is
  // exactly where the timeline ends -- not the run's wall-clock duration,
  // which includes setup the grid never shows.
  const runDuration = useMemo(() => {
    if (!isTerminal) return null;
    const end = timelineDuration(timings);
    return end > 0 ? end : (serverElapsed ?? null);
  }, [isTerminal, timings, serverElapsed]);

  if (isLoading && !matrix) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!matrix) {
    return (
      <Typography color="text.secondary">No verdict data available.</Typography>
    );
  }

  return (
    <RunClockProvider
      active={!isTerminal}
      serverElapsed={serverElapsed}
      runDuration={runDuration}
    >
      <Stack spacing={3}>
        <KpiRow
          matrix={matrix}
          testRun={testRun}
          isRunning={!isTerminal}
          testIds={testIds}
          timings={timings}
          onViewFailures={onViewFailures}
        />

        <RequirementTable
          matrix={matrix}
          density={effectiveDensity}
          onDensityChange={setDensity}
          hideDensityControl={isNarrow}
          timings={timings}
          onViewRequirement={onViewRequirement}
          onViewMetric={onViewMetric}
        />

        {isTerminal && <BreakdownsDrawer testRunId={testRunId} />}
      </Stack>
    </RunClockProvider>
  );
}

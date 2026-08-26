'use client';

import React, { useMemo } from 'react';
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
import { useDensityPreference } from './hooks/useDensityPreference';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface RunSummaryProps {
  testRunId: string;
  testRun: TestRunDetail;
  onViewRequirement?: (id: string) => void;
  onViewMetric?: (name: string, reqId?: string) => void;
  onViewFailures?: () => void;
}

const EMPTY_SET = new Set<string>();

export default function RunSummary({
  testRunId,
  testRun,
  onViewRequirement,
  onViewMetric,
  onViewFailures,
}: RunSummaryProps) {
  const { matrix, isLoading, isTerminal } = useTestRunLive(testRunId);
  const { density, setDensity } = useDensityPreference({ isTerminal });

  // Below ~720px the Numbers+shape strip is too small to read and Detail's
  // fixed name column eats the row -- force Numbers and hide the control,
  // without touching the persisted preference so it's restored on widen.
  const isNarrow = useMediaQuery('(max-width:720px)');
  const effectiveDensity = isNarrow ? 'numbers' : density;

  const testIds = useMemo(() => (matrix?.test_ids ?? []).map(String), [matrix]);

  const generatingIds = useMemo<Set<string>>(() => {
    if (!matrix) return EMPTY_SET;
    const ids = matrix.test_status;
    if (!ids) return EMPTY_SET;
    // test_status is a char-per-test string: G=generating, E=evaluating, .=idle
    const testIds = matrix.test_ids ?? [];
    const result = new Set<string>();
    for (let i = 0; i < ids.length && i < testIds.length; i++) {
      if (ids[i] === 'G') result.add(String(testIds[i]));
    }
    return result;
  }, [matrix]);

  const evaluatingIds = useMemo<Set<string>>(() => {
    if (!matrix) return EMPTY_SET;
    const ids = matrix.test_status;
    if (!ids) return EMPTY_SET;
    const testIds = matrix.test_ids ?? [];
    const result = new Set<string>();
    for (let i = 0; i < ids.length && i < testIds.length; i++) {
      if (ids[i] === 'E') result.add(String(testIds[i]));
    }
    return result;
  }, [matrix]);

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
    <RunClockProvider active={!isTerminal}>
      <Stack spacing={3}>
        <KpiRow
          matrix={matrix}
          testRun={testRun}
          isRunning={!isTerminal}
          testIds={testIds}
          generatingIds={generatingIds}
          evaluatingIds={evaluatingIds}
          onViewFailures={onViewFailures}
        />

        <RequirementTable
          matrix={matrix}
          density={effectiveDensity}
          onDensityChange={setDensity}
          hideDensityControl={isNarrow}
          generatingIds={generatingIds}
          evaluatingIds={evaluatingIds}
          onViewRequirement={onViewRequirement}
          onViewMetric={onViewMetric}
        />

        {isTerminal && <BreakdownsDrawer testRunId={testRunId} />}
      </Stack>
    </RunClockProvider>
  );
}

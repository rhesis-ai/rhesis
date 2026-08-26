'use client';

import React, { useMemo } from 'react';
import { Box, Grid, LinearProgress, useTheme } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import KpiCard from './KpiCard';
import { deriveRunStatus } from './run-status';
import { formatDuration } from './run-meta';
import type {
  VerdictMatrix,
  TestRunDetail,
} from '@/utils/api-client/interfaces/test-run';

interface KpiRowProps {
  matrix: VerdictMatrix;
  testRun: TestRunDetail;
  isRunning: boolean;
  onViewFailures?: () => void;
}

export default function KpiRow({
  matrix,
  testRun,
  isRunning,
  onViewFailures,
}: KpiRowProps) {
  const theme = useTheme();
  const { kpis } = matrix;

  const durationDisplay = useMemo(() => {
    if (isRunning) return undefined;
    const { duration } = deriveRunStatus(testRun);
    return duration !== null
      ? `Ran for ${formatDuration(duration)}`
      : undefined;
  }, [testRun, isRunning]);

  const passRateDisplay = useMemo(() => {
    if (kpis.pass_rate === null) return '--';
    return `${Math.round(kpis.pass_rate * 100)}%`;
  }, [kpis.pass_rate]);

  const passRateIcon = useMemo(() => {
    if (kpis.pass_rate === null) return <PlayCircleOutlineIcon />;
    if (kpis.pass_rate >= 0.67)
      return (
        <CheckCircleOutlineIcon sx={{ color: theme.palette.success.main }} />
      );
    if (kpis.pass_rate >= 0.33)
      return (
        <WarningAmberOutlinedIcon sx={{ color: theme.palette.warning.main }} />
      );
    return <CancelOutlinedIcon sx={{ color: theme.palette.error.main }} />;
  }, [kpis.pass_rate, theme]);

  const testsProgress =
    kpis.tests_total > 0 ? (kpis.tests_executed / kpis.tests_total) * 100 : 0;

  return (
    <Box sx={{ mb: 4 }}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Pass Rate"
            value={passRateDisplay}
            subtitle={
              kpis.pass_rate !== null
                ? `${kpis.verdicts_resolved} verdicts resolved`
                : undefined
            }
            icon={passRateIcon}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Tests Executed"
            value={`${kpis.tests_executed}/${kpis.tests_total}`}
            subtitle={durationDisplay}
            icon={<PlayCircleOutlineIcon />}
            trend={
              isRunning ? (
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
            title="Metric Verdicts"
            value={`${kpis.verdicts_resolved}/${kpis.verdicts_planned}`}
            subtitle={
              kpis.verdicts_planned > 0
                ? `${Math.round((kpis.verdicts_resolved / kpis.verdicts_planned) * 100)}% complete`
                : undefined
            }
            icon={<CheckCircleOutlineIcon />}
            infoTooltip="Each test/metric pair produces one verdict. Shows verdicts resolved out of the total planned for this run."
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiCard
            title="Failures"
            value={kpis.failures}
            icon={
              <ErrorOutlineIcon
                sx={{
                  color:
                    kpis.failures > 0
                      ? theme.palette.error.main
                      : theme.palette.text.secondary,
                }}
              />
            }
            onClick={kpis.failures > 0 ? onViewFailures : undefined}
          />
        </Grid>
      </Grid>
    </Box>
  );
}

'use client';

import React, { useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Grid,
  IconButton,
  Tooltip,
  useTheme,
} from '@mui/material';
import BlockIcon from '@mui/icons-material/Block';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import TimerOutlinedIcon from '@mui/icons-material/TimerOutlined';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import Link from 'next/link';
import {
  PassFailStats,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { formatDate } from '@/utils/date';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';
import { experimentHref } from '@/utils/experiment-links';
import { BiotechIcon } from '@/components/icons';

interface TestRunHeaderProps {
  testRun: TestRunDetail;
  testResults: TestResultDetail[];
  overallStats?: PassFailStats;
  loading?: boolean;
  onRefresh?: () => void;
}

interface SummaryCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  color?: 'primary' | 'success' | 'error' | 'warning' | 'info';
}

function SummaryCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendValue,
  color = 'primary',
}: SummaryCardProps) {
  const theme = useTheme();

  const iconColors = {
    primary: theme.palette.primary.main,
    success: theme.palette.success.main,
    error: theme.palette.error.main,
    warning: theme.palette.warning.main,
    info: theme.palette.info.main,
  };

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <CardContent sx={{ flexGrow: 1, p: 3 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            mb: 2,
          }}
        >
          <Typography variant="body2" color="text.secondary" fontWeight={500}>
            {title}
          </Typography>
          <Box
            sx={{
              color: iconColors[color],
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {icon}
          </Box>
        </Box>

        <Typography variant="h4" fontWeight={600} sx={{ mb: 1 }}>
          {value}
        </Typography>

        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}

        {trend && trendValue && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 1, gap: 0.5 }}>
            {trend === 'up' && (
              <TrendingUpIcon fontSize="small" color="success" />
            )}
            {trend === 'down' && (
              <TrendingDownIcon fontSize="small" color="error" />
            )}
            <Typography
              variant="caption"
              color={
                trend === 'up'
                  ? 'success.main'
                  : trend === 'down'
                    ? 'error.main'
                    : 'text.secondary'
              }
              fontWeight={500}
            >
              {trendValue}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

export default function TestRunHeader({
  testRun,
  testResults,
  overallStats,
  loading: _loading = false,
  onRefresh,
}: TestRunHeaderProps) {
  const theme = useTheme();

  // Determine if this is a multi-turn test set
  const isMultiTurn =
    testRun.test_configuration?.test_set?.test_set_type?.type_value
      ?.toLowerCase()
      .includes('multi-turn') || false;

  // Calculate statistics
  const stats = useMemo(() => {
    let total: number;
    let passed: number;
    let failed: number;
    let executionErrors: number;
    let totalTurns = 0;
    let testsWithTurnData = 0;

    if (overallStats) {
      total = overallStats.total;
      passed = overallStats.passed;
      failed = overallStats.failed;
      executionErrors = total - passed - failed;
    } else {
      total = testResults.length;
      passed = 0;
      failed = 0;
      executionErrors = 0;

      testResults.forEach(result => {
        const status = getEffectiveTestResultStatus(result);
        if (status === 'Error') {
          executionErrors++;
        } else if (status === 'Pass') {
          passed++;
        } else if (status === 'Fail') {
          failed++;
        }

        if (isMultiTurn && result.test_output) {
          const turns =
            result.test_output.turns_used ||
            result.test_output.stats?.total_turns;
          if (turns) {
            totalTurns += turns;
            testsWithTurnData++;
          }
        }
      });
    }

    const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : '0.0';
    const avgTurnDepth =
      testsWithTurnData > 0 ? (totalTurns / testsWithTurnData).toFixed(0) : '0';

    // Calculate duration
    const startedAt = testRun.attributes?.started_at;
    const completedAt = testRun.attributes?.completed_at;
    let duration = 'N/A';
    if (
      startedAt &&
      completedAt &&
      typeof startedAt === 'string' &&
      typeof completedAt === 'string'
    ) {
      const start = new Date(startedAt).getTime();
      const end = new Date(completedAt).getTime();
      const diffMs = Math.abs(end - start);
      const diffMins = Math.floor(diffMs / 60000);
      const diffSecs = Math.floor((diffMs % 60000) / 1000);
      duration = `${diffMins}m ${diffSecs}s`;
    } else if (startedAt) {
      duration = 'In Progress';
    }

    // Determine status from testRun.status or calculate it
    let status:
      | 'completed'
      | 'in_progress'
      | 'failed'
      | 'partial'
      | 'cancelled'
      | 'queued' = 'completed';
    let statusColor: 'success' | 'info' | 'error' | 'warning' | 'default' =
      'success';
    let statusLabel = 'Completed';

    // Use backend status if available
    const backendStatus = testRun.status?.name?.toLowerCase();

    if (backendStatus === 'cancelled') {
      status = 'cancelled';
      statusColor = 'default';
      statusLabel = 'Cancelled';
      if (startedAt) duration = 'Cancelled';
    } else if (backendStatus === 'queued') {
      status = 'queued';
      statusColor = 'default';
      statusLabel = 'Queued';
      duration = 'Queued';
    } else if (backendStatus === 'progress') {
      status = 'in_progress';
      statusColor = 'info';
      statusLabel = 'In Progress';
    } else if (backendStatus === 'partial') {
      status = 'partial';
      statusColor = 'warning';
      statusLabel = 'Partial';
    } else if (backendStatus === 'failed') {
      status = 'failed';
      statusColor = 'error';
      statusLabel = 'Failed';
    } else if (backendStatus === 'completed') {
      status = 'completed';
      // Completed means all tests executed (regardless of assertion results)
      statusColor = 'success';
      statusLabel = 'Completed';
    } else {
      // Fallback: calculate from attributes
      if (!completedAt && startedAt) {
        status = 'in_progress';
        statusColor = 'info';
        statusLabel = 'In Progress';
      } else if (
        completedAt &&
        executionErrors > 0 &&
        executionErrors < total
      ) {
        status = 'partial';
        statusColor = 'warning';
        statusLabel = 'Partial';
      } else if (executionErrors === total && total > 0) {
        status = 'failed';
        statusColor = 'error';
        statusLabel = 'Failed';
      } else if (completedAt) {
        // If completed, all tests executed (even if some failed assertions)
        status = 'completed';
        statusColor = 'success';
        statusLabel = 'Completed';
      }
    }

    return {
      total,
      passed,
      failed,
      executionErrors,
      passRate,
      avgTurnDepth,
      duration,
      status,
      statusColor,
      statusLabel,
    };
  }, [testResults, testRun, isMultiTurn]);

  const totalExpected =
    testRun.test_configuration?.test_set?.attributes?.metadata?.total_tests;

  const isInProgress = stats.status === 'in_progress';

  return (
    <Box sx={{ mb: 4 }}>
      <Grid container spacing={3}>
        {/* Pass Rate Card */}
        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <SummaryCard
            title="Pass Rate"
            value={`${stats.passRate}%`}
            subtitle={`${stats.passed} of ${stats.total} tests`}
            icon={
              parseFloat(stats.passRate) > 66 ? (
                <CheckCircleOutlineIcon />
              ) : parseFloat(stats.passRate) >= 33 ? (
                <WarningAmberOutlinedIcon />
              ) : (
                <CancelOutlinedIcon />
              )
            }
            color={
              parseFloat(stats.passRate) > 66
                ? 'success'
                : parseFloat(stats.passRate) >= 33
                  ? 'warning'
                  : 'error'
            }
          />
        </Grid>

        {/* Tests Executed Card */}
        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <Card
            sx={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <CardContent sx={{ flexGrow: 1, p: 3 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  mb: 2,
                }}
              >
                <Typography
                  variant="body2"
                  color="text.secondary"
                  fontWeight={500}
                >
                  Tests Executed
                </Typography>
                <Box
                  sx={{
                    color: theme.palette.primary.main,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  {isInProgress && onRefresh ? (
                    <Tooltip title="Refresh">
                      <IconButton size="small" onClick={onRefresh}>
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  ) : (
                    <PlayCircleOutlineIcon />
                  )}
                </Box>
              </Box>

              <Typography variant="h4" fontWeight={600} sx={{ mb: 1 }}>
                {totalExpected
                  ? `${stats.total}/${totalExpected}`
                  : stats.total}
              </Typography>

              <Typography variant="body2" color="text.secondary">
                {isMultiTurn
                  ? `Avg ${stats.avgTurnDepth} turns`
                  : stats.executionErrors > 0
                    ? `${stats.passed} passed, ${stats.failed} failed, ${stats.executionErrors} errors`
                    : `${stats.passed} passed, ${stats.failed} failed`}
              </Typography>

              {testRun.experiment_id && (
                <Link
                  href={experimentHref(
                    testRun.experiment_id,
                    typeof testRun.attributes?.parameter_version === 'string'
                      ? testRun.attributes.parameter_version
                      : undefined
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: 'none' }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      mt: 1,
                      '&:hover': {
                        '& .experiment-name': {
                          color: theme.palette.primary.main,
                          textDecoration: 'underline',
                        },
                      },
                    }}
                  >
                    <BiotechIcon
                      sx={{ fontSize: 16, color: 'text.secondary' }}
                    />
                    <Typography
                      variant="body2"
                      className="experiment-name"
                      sx={{
                        transition: 'color 0.2s',
                        color: 'text.secondary',
                        fontWeight: 200,
                      }}
                    >
                      {(testRun.attributes
                        ?.parameter_experiment_name as string) || 'Experiment'}
                    </Typography>
                    {typeof testRun.attributes?.parameter_version ===
                      'string' && (
                      <Chip
                        label={shortVersion(
                          testRun.attributes?.parameter_version as string
                        )}
                        size="small"
                        variant="outlined"
                        sx={{ ml: 0.5 }}
                      />
                    )}
                    <OpenInNewIcon
                      sx={{
                        fontSize: 12,
                        color: 'text.disabled',
                      }}
                    />
                  </Box>
                </Link>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Duration Card */}
        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <SummaryCard
            title="Duration"
            value={stats.duration}
            subtitle={
              testRun.attributes?.started_at &&
              typeof testRun.attributes.started_at === 'string'
                ? formatDate(testRun.attributes.started_at)
                : 'N/A'
            }
            icon={<TimerOutlinedIcon />}
            color="info"
          />
        </Grid>

        {/* Status Card */}
        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <Card
            sx={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <CardContent sx={{ flexGrow: 1, p: 3 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Typography
                  variant="body2"
                  color="text.secondary"
                  fontWeight={500}
                >
                  Status
                </Typography>
                <Chip
                  label={stats.statusLabel}
                  color={stats.statusColor}
                  icon={
                    stats.status === 'cancelled' ? (
                      <BlockIcon />
                    ) : stats.status === 'queued' ? (
                      <HourglassEmptyIcon />
                    ) : stats.status === 'in_progress' ? (
                      <PlayCircleOutlineIcon />
                    ) : stats.status === 'partial' ? (
                      <WarningAmberOutlinedIcon />
                    ) : stats.status === 'failed' ? (
                      <CancelOutlinedIcon />
                    ) : (
                      <CheckCircleOutlineIcon />
                    )
                  }
                  size="medium"
                  sx={{ fontWeight: 600 }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

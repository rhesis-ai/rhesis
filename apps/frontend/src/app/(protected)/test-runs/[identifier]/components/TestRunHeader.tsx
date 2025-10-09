'use client';

import React, { useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Grid,
  useTheme,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import TimerOutlinedIcon from '@mui/icons-material/TimerOutlined';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import Link from 'next/link';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { formatDate } from '@/utils/date';

interface TestRunHeaderProps {
  testRun: TestRunDetail;
  testResults: TestResultDetail[];
  loading?: boolean;
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
  loading = false,
}: TestRunHeaderProps) {
  const theme = useTheme();

  // Calculate statistics
  const stats = useMemo(() => {
    const total = testResults.length;
    const passed = testResults.filter(result => {
      const metrics = result.test_metrics?.metrics;
      if (!metrics) return false;
      return Object.values(metrics).every(metric => metric.is_successful);
    }).length;
    const failed = total - passed;
    const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : '0.0';

    // Calculate duration
    const startedAt = testRun.attributes?.started_at;
    const completedAt = testRun.attributes?.completed_at;
    let duration = 'N/A';
    if (startedAt && completedAt) {
      const start = new Date(startedAt).getTime();
      const end = new Date(completedAt).getTime();
      const diffMs = end - start;
      const diffMins = Math.floor(diffMs / 60000);
      const diffSecs = Math.floor((diffMs % 60000) / 1000);
      duration = `${diffMins}m ${diffSecs}s`;
    } else if (startedAt) {
      duration = 'In Progress';
    }

    // Determine status
    let status: 'completed' | 'in_progress' | 'failed' = 'completed';
    let statusColor: 'success' | 'info' | 'error' = 'success';

    if (!completedAt && startedAt) {
      status = 'in_progress';
      statusColor = 'info';
    } else if (completedAt && failed > 0) {
      status = 'completed';
      statusColor = passed > failed ? 'success' : 'error';
    }

    return {
      total,
      passed,
      failed,
      passRate,
      duration,
      status,
      statusColor,
    };
  }, [testResults, testRun]);

  return (
    <Box sx={{ mb: 4 }}>
      <Grid container spacing={3}>
        {/* Pass Rate Card */}
        <Grid item xs={12} sm={6} md={3}>
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
        <Grid item xs={12} sm={6} md={3}>
          <SummaryCard
            title="Tests Executed"
            value={stats.total}
            subtitle={`${stats.passed} passed, ${stats.failed} failed`}
            icon={<PlayCircleOutlineIcon />}
            color="primary"
          />
        </Grid>

        {/* Duration Card */}
        <Grid item xs={12} sm={6} md={3}>
          <SummaryCard
            title="Duration"
            value={stats.duration}
            subtitle={
              testRun.attributes?.started_at
                ? formatDate(testRun.attributes.started_at)
                : 'N/A'
            }
            icon={<TimerOutlinedIcon />}
            color="info"
          />
        </Grid>

        {/* Status Card */}
        <Grid item xs={12} sm={6} md={3}>
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
                  mb: 2,
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
                  label={
                    stats.status === 'in_progress' ? 'In Progress' : 'Completed'
                  }
                  color={stats.statusColor}
                  icon={
                    stats.status === 'in_progress' ? (
                      <PlayCircleOutlineIcon />
                    ) : stats.statusColor === 'success' ? (
                      <CheckCircleOutlineIcon />
                    ) : (
                      <CancelOutlinedIcon />
                    )
                  }
                  size="medium"
                  sx={{ fontWeight: 600 }}
                />
              </Box>

              {testRun.test_configuration?.test_set?.id ? (
                <Link
                  href={`/test-sets/${testRun.test_configuration.test_set.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: 'none' }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      '&:hover': {
                        '& .test-set-name': {
                          color: theme.palette.primary.main,
                          textDecoration: 'underline',
                        },
                      },
                    }}
                  >
                    <Typography
                      variant="subtitle1"
                      className="test-set-name"
                      sx={{
                        transition: 'color 0.2s',
                        color: 'text.secondary',
                        fontWeight: 500,
                      }}
                    >
                      {testRun.test_configuration.test_set.name ||
                        'Unknown Test Set'}
                    </Typography>
                    <OpenInNewIcon
                      sx={{
                        fontSize: 14,
                        color: 'text.disabled',
                      }}
                    />
                  </Box>
                </Link>
              ) : (
                <Typography
                  variant="subtitle1"
                  color="text.secondary"
                  fontWeight={500}
                >
                  {testRun.test_configuration?.test_set?.name ||
                    'Unknown Test Set'}
                </Typography>
              )}

              {testRun.test_configuration?.endpoint?.id ? (
                <Link
                  href={`/endpoints/${testRun.test_configuration.endpoint.id}`}
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
                        '& .endpoint-name': {
                          color: theme.palette.primary.main,
                          textDecoration: 'underline',
                        },
                      },
                    }}
                  >
                    <Typography
                      variant="body2"
                      className="endpoint-name"
                      sx={{
                        transition: 'color 0.2s',
                        color: 'text.secondary',
                        fontWeight: 200,
                      }}
                    >
                      Endpoint:{' '}
                      {testRun.test_configuration.endpoint.name ||
                        testRun.attributes?.environment ||
                        'development'}
                    </Typography>
                    <OpenInNewIcon
                      sx={{
                        fontSize: 12,
                        color: 'text.disabled',
                      }}
                    />
                  </Box>
                </Link>
              ) : (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  fontWeight={500}
                  sx={{ display: 'block', mt: 1 }}
                >
                  Endpoint:{' '}
                  {testRun.test_configuration?.endpoint?.name ||
                    testRun.attributes?.environment ||
                    'development'}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

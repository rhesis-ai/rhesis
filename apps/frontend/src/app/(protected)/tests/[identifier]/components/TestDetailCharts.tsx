'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  Alert,
  Card,
  CardContent,
  useTheme,
  Grid,
  Chip,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import Link from 'next/link';
import {
  LineChart,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { formatDuration } from '@/utils/format-duration';
import { IndividualTestStats } from '@/utils/api-client/interfaces/individual-test-stats';
import BasePieChart from '@/components/common/BasePieChart';
import BaseChartsGrid from '@/components/common/BaseChartsGrid';
import { useChartColors } from '@/components/layout/BaseChartColors';

interface TestDetailChartsProps {
  testId: string;
  sessionToken: string;
}

interface LastTestRunCardProps {
  lastRunStatus: boolean | null;
  lastRunName?: string;
  lastRunDate?: string;
  lastRunExecutionTime?: number;
  lastRunId?: string;
  lastRunMetrics?: {
    [metricName: string]: {
      is_successful: boolean;
      score: number;
      reason: string | null;
    };
  };
}

function LastTestRunCard({
  lastRunStatus,
  lastRunName,
  lastRunDate,
  lastRunExecutionTime,
  lastRunId,
  lastRunMetrics,
}: LastTestRunCardProps) {
  const theme = useTheme();
  const { palettes } = useChartColors();

  // Determine status color and text - matching pie chart colors
  const getStatusColor = () => {
    if (lastRunStatus === null) return theme.palette.text.secondary;
    // Use pie palette colors: blue/cyan for passed, orange for failed
    return lastRunStatus ? palettes.pie[0] : palettes.pie[1];
  };

  const getStatusText = () => {
    if (lastRunStatus === null) return 'No Runs';
    return lastRunStatus ? 'Passed' : 'Failed';
  };

  const getStatusIcon = () => {
    if (lastRunStatus === null) return null;
    return lastRunStatus ? (
      <CheckCircleOutlineIcon
        sx={{ fontSize: 20, mr: 0.5, color: theme.palette.text.secondary }}
      />
    ) : (
      <CancelOutlinedIcon
        sx={{ fontSize: 20, mr: 0.5, color: theme.palette.text.secondary }}
      />
    );
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Count metric results
  const getMetricCounts = () => {
    if (!lastRunMetrics) return null;
    const metrics = Object.values(lastRunMetrics);
    const passed = metrics.filter(m => m.is_successful).length;
    const failed = metrics.length - passed;
    return { passed, failed, total: metrics.length };
  };

  const metricCounts = getMetricCounts();

  return (
    <Card
      elevation={1}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <CardContent
        sx={{
          pt: 0.25,
          px: 0.5,
          pb: 0.25,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          '&:last-child': { pb: 0.25 },
        }}
      >
        {/* Card Title */}
        <Typography
          variant="subtitle2"
          component="h3"
          sx={{
            mb: 0,
            px: 0,
            textAlign: 'center',
          }}
        >
          Last Test Run
        </Typography>

        {/* Status Display */}
        <Box
          sx={{
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            gap: 1,
            px: 1,
          }}
        >
          {/* Status with Icon */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              {getStatusIcon()}
              <Typography
                variant="h6"
                component="div"
                sx={{
                  fontWeight: 600,
                  color: getStatusColor(),
                }}
              >
                {getStatusText()}
              </Typography>
            </Box>
          </Box>

          {/* Test Run Name */}
          {lastRunName && lastRunId && (
            <Link
              href={`/test-runs/${lastRunId}`}
              style={{ textDecoration: 'none' }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontSize: theme.typography.caption.fontSize,
                  textAlign: 'center',
                  fontWeight: 500,
                  color: theme.palette.primary.main,
                  '&:hover': {
                    textDecoration: 'underline',
                  },
                  cursor: 'pointer',
                }}
              >
                {lastRunName}
              </Typography>
            </Link>
          )}
          {lastRunName && !lastRunId && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                fontSize: theme.typography.caption.fontSize,
                textAlign: 'center',
                fontWeight: 500,
              }}
            >
              {lastRunName}
            </Typography>
          )}

          {/* Metrics Info */}
          {metricCounts && (
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                justifyContent: 'center',
                flexWrap: 'wrap',
              }}
            >
              <Chip
                size="small"
                label={`${metricCounts.passed}/${metricCounts.total} metrics passed`}
                sx={{
                  fontSize: theme.typography.caption.fontSize,
                  height: 24,
                }}
              />
            </Box>
          )}

          {/* Additional Info - Execution Time and Date on separate lines */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 0.5,
              alignItems: 'center',
            }}
          >
            {lastRunExecutionTime !== undefined && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <AccessTimeIcon
                  sx={{ fontSize: 14, color: theme.palette.text.secondary }}
                />
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontSize: theme.typography.caption.fontSize }}
                >
                  {formatDuration(lastRunExecutionTime)}
                </Typography>
              </Box>
            )}
            {lastRunDate && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <CalendarTodayIcon
                  sx={{ fontSize: 14, color: theme.palette.text.secondary }}
                />
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontSize: theme.typography.caption.fontSize }}
                >
                  {formatDate(lastRunDate)}
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

interface SinglePointChartProps {
  title: string;
  value: number;
  label: string;
  subtitle?: string;
  color?: string;
  formatValue?: (value: number) => string;
  legendLabel?: string;
  tooltipDetails?: {
    label: string;
    value: string | number;
  }[];
}

function SinglePointChart({
  title,
  value,
  label,
  subtitle,
  color,
  formatValue,
  legendLabel,
  tooltipDetails,
}: SinglePointChartProps) {
  const theme = useTheme();
  const { palettes } = useChartColors();

  // Create data with single point
  const data = [{ name: label, value: value }];

  // Use theme chart colors for consistency
  const chartColor = color || palettes.line[0];

  // Legend display name
  const displayLegendLabel = legendLabel || label;

  // Custom tooltip with comprehensive details
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const displayValue = formatValue
        ? formatValue(payload[0].value)
        : payload[0].value;
      return (
        <Box
          sx={{
            backgroundColor: 'background.paper',
            border: 1,
            borderColor: 'divider',
            borderRadius: theme.shape.borderRadius,
            p: '10px 14px',
            fontSize: theme.typography.caption.fontSize,
            color: 'text.primary',
            minWidth: '150px',
          }}
        >
          <Box sx={{ mb: '6px' }}>
            <Typography
              component="span"
              sx={{
                color: 'text.secondary',
                fontSize: theme.typography.caption.fontSize,
              }}
            >
              Value:{' '}
            </Typography>
            <Typography
              component="span"
              sx={{
                fontWeight: 600,
                fontSize: theme.typography.caption.fontSize,
              }}
            >
              {displayValue}
            </Typography>
          </Box>
          {tooltipDetails &&
            tooltipDetails.map(detail => (
              <Box
                key={detail.label}
                sx={{ mb: '4px', fontSize: theme.typography.caption.fontSize }}
              >
                <Typography
                  component="span"
                  sx={{
                    color: 'text.secondary',
                    fontSize: theme.typography.caption.fontSize,
                  }}
                >
                  {detail.label}:{' '}
                </Typography>
                <Typography
                  component="span"
                  sx={{ fontSize: theme.typography.caption.fontSize }}
                >
                  {detail.value}
                </Typography>
              </Box>
            ))}
        </Box>
      );
    }
    return null;
  };

  return (
    <Card
      elevation={1}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <CardContent
        sx={{
          p: 0.5,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          '&:last-child': { pb: 0.25 },
        }}
      >
        {/* Card Title */}
        <Typography
          variant="subtitle2"
          component="h3"
          sx={{
            mb: 1,
            px: 0.5,
            textAlign: 'center',
          }}
        >
          {title}
        </Typography>

        {/* Chart */}
        <Box sx={{ flexGrow: 1, minHeight: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={theme.palette.divider}
              />
              <XAxis
                dataKey="name"
                type="category"
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                axisLine={{ stroke: theme.palette.divider }}
              />
              <YAxis
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                axisLine={{ stroke: theme.palette.divider }}
                domain={[0, (dataMax: number) => Math.ceil(dataMax * 1.2)]}
                width={40}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="value"
                stroke={chartColor}
                strokeWidth={2}
                dot={{ fill: chartColor, r: 5 }}
                activeDot={{ r: 7 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Box>

        {/* Subtitle */}
        {subtitle && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              fontSize: theme.typography.caption.fontSize,
              textAlign: 'center',
              mt: 0.5,
            }}
          >
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

export default function TestDetailCharts({
  testId,
  sessionToken,
}: TestDetailChartsProps) {
  const theme = useTheme();
  const [stats, setStats] = useState<IndividualTestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        setError(null);

        const apiFactory = new ApiClientFactory(sessionToken);
        const testsClient = apiFactory.getTestsClient();

        const data = await testsClient.getIndividualTestStats(testId, {
          recent_runs_limit: 5,
        });

        setStats(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load statistics'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [testId, sessionToken]);

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight={200}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!stats || stats.overall_summary.total_executions === 0) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No test execution data available yet. Run this test to see statistics.
      </Alert>
    );
  }

  const { overall_summary, recent_runs } = stats;

  // Prepare pass rate pie chart data
  const passRateData = [
    {
      name: 'Passed',
      value: overall_summary.passed,
      fullName: `Passed: ${overall_summary.passed}`,
    },
    {
      name: 'Failed',
      value: overall_summary.failed,
      fullName: `Failed: ${overall_summary.failed}`,
    },
  ].filter(item => item.value > 0);

  return (
    <BaseChartsGrid>
      {/* Last Test Run Status */}
      <LastTestRunCard
        lastRunStatus={
          recent_runs.length > 0 ? recent_runs[0].overall_passed : null
        }
        lastRunName={
          recent_runs.length > 0 ? recent_runs[0].test_run_name : undefined
        }
        lastRunDate={
          recent_runs.length > 0 ? recent_runs[0].created_at : undefined
        }
        lastRunExecutionTime={
          recent_runs.length > 0 ? recent_runs[0].execution_time_ms : undefined
        }
        lastRunId={
          recent_runs.length > 0 ? recent_runs[0].test_run_id : undefined
        }
        lastRunMetrics={
          recent_runs.length > 0 ? recent_runs[0].metrics : undefined
        }
      />

      {/* Pass Rate Pie Chart */}
      <BasePieChart
        title="Overall Pass Rate"
        data={passRateData}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
        variant="test-results"
      />

      {/* Test Runs */}
      <SinglePointChart
        title="Total Executions"
        value={overall_summary.total_executions}
        label="Total"
        subtitle={`${overall_summary.total_test_runs} test runs`}
        tooltipDetails={[
          { label: 'Test Runs', value: overall_summary.total_test_runs },
          {
            label: 'Avg per Run',
            value: `${(overall_summary.total_executions / overall_summary.total_test_runs).toFixed(1)} executions`,
          },
          { label: 'Passed', value: overall_summary.passed },
          { label: 'Failed', value: overall_summary.failed },
        ]}
      />

      {/* Average Execution Time */}
      <SinglePointChart
        title="Avg Execution Time (seconds)"
        value={overall_summary.avg_execution_time_ms / 1000}
        label="Average"
        subtitle="per execution"
        formatValue={seconds => `${seconds.toFixed(2)}s`}
        tooltipDetails={[
          {
            label: 'Total Executions',
            value: overall_summary.total_executions,
          },
          {
            label: 'Total Time',
            value: formatDuration(
              overall_summary.avg_execution_time_ms *
                overall_summary.total_executions
            ),
          },
          {
            label: 'Min Time',
            value:
              '~' + formatDuration(overall_summary.avg_execution_time_ms * 0.7),
          },
          {
            label: 'Max Time',
            value:
              '~' + formatDuration(overall_summary.avg_execution_time_ms * 1.3),
          },
        ]}
      />
    </BaseChartsGrid>
  );
}

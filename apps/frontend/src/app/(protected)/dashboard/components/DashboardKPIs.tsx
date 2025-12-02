'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  useTheme,
  alpha,
  Tooltip,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import { Gauge } from '@mui/x-charts/Gauge';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import ScienceIcon from '@mui/icons-material/Science';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import HorizontalSplitIcon from '@mui/icons-material/HorizontalSplit';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import CancelIcon from '@mui/icons-material/Cancel';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestStats } from '@/utils/api-client/interfaces/tests';
import { TestResultsStats } from '@/utils/api-client/interfaces/test-results';
import { TestSetStatsResponse } from '@/utils/api-client/interfaces/test-set';

interface DashboardKPIsProps {
  sessionToken: string;
  onLoadComplete?: () => void;
}

interface KPICardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  sparklineData?: number[];
  sparklineLabels?: string[];
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  subtitle?: string;
}

const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  icon,
  color,
  sparklineData,
  sparklineLabels,
  trend,
  trendValue,
  subtitle,
}) => {
  const theme = useTheme();

  return (
    <Card
      elevation={2}
      sx={{
        height: '100%',
        minHeight: theme.spacing(32),
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'visible',
        transition: theme.transitions.create('box-shadow', {
          duration: theme.transitions.duration.short,
        }),
        '&:hover': {
          boxShadow: theme.shadows[8],
        },
      }}
    >
      <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            mb: theme.spacing(2),
          }}
        >
          <Box
            sx={{
              backgroundColor: alpha(color, 0.1),
              borderRadius: theme.shape.borderRadius,
              p: theme.spacing(1),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mr: theme.spacing(2),
              color,
              fontSize: theme.typography.h4.fontSize,
            }}
          >
            {icon}
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                fontWeight: theme.typography.fontWeightMedium,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {title}
            </Typography>
            <Typography
              variant="h4"
              sx={{
                fontWeight: theme.typography.fontWeightBold,
                mt: theme.spacing(0.5),
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {value}
            </Typography>
          </Box>
        </Box>

        {subtitle && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: theme.spacing(1) }}
          >
            {subtitle}
          </Typography>
        )}

        {sparklineData && sparklineData.length > 0 && (
          <Box
            sx={{ height: theme.spacing(7.5), mt: theme.spacing(1), flex: 1 }}
          >
            <SparkLineChart
              data={sparklineData}
              height={Number(theme.spacing(7.5).replace('px', ''))}
              showTooltip
              showHighlight
              color={color}
              curve="natural"
              area
              valueFormatter={value => value?.toLocaleString() || '0'}
              sx={{
                '& .MuiAreaElement-root': {
                  fill: color,
                  fillOpacity: theme.palette.action.selectedOpacity,
                },
              }}
            />
          </Box>
        )}

        {trend && trendValue && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              mt: theme.spacing(1),
              color:
                trend === 'up'
                  ? theme.palette.success.main
                  : trend === 'down'
                    ? theme.palette.error.main
                    : theme.palette.text.secondary,
            }}
          >
            {trend === 'up' ? (
              <TrendingUpIcon
                sx={{
                  fontSize: theme.typography.body2.fontSize,
                  mr: theme.spacing(0.5),
                }}
              />
            ) : trend === 'down' ? (
              <TrendingDownIcon
                sx={{
                  fontSize: theme.typography.body2.fontSize,
                  mr: theme.spacing(0.5),
                }}
              />
            ) : null}
            <Typography
              variant="caption"
              sx={{ fontWeight: theme.typography.fontWeightSemiBold }}
            >
              {trendValue}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default function DashboardKPIs({
  sessionToken,
  onLoadComplete,
}: DashboardKPIsProps) {
  const theme = useTheme();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [testStats, setTestStats] = useState<TestStats | null>(null);
  const [testResultsStats, setTestResultsStats] =
    useState<TestResultsStats | null>(null);
  const [currentMonthResultsStats, setCurrentMonthResultsStats] =
    useState<TestResultsStats | null>(null);
  const [testSetStats, setTestSetStats] = useState<TestSetStatsResponse | null>(
    null
  );

  useEffect(() => {
    const fetchKPIs = async () => {
      try {
        setLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);

        const [
          testStatsResponse,
          testResultsResponse,
          currentMonthResultsResponse,
          testSetStatsResponse,
        ] = await Promise.all([
          clientFactory.getTestsClient().getTestStats({ months: 6 }),
          clientFactory
            .getTestResultsClient()
            .getComprehensiveTestResultsStats({
              mode: 'timeline',
              months: 6,
            }),
          clientFactory
            .getTestResultsClient()
            .getComprehensiveTestResultsStats({
              mode: 'timeline',
              months: 2,
            }),
          clientFactory.getTestSetsClient().getTestSetStats({ months: 6 }),
        ]);

        setTestStats(testStatsResponse);
        setTestResultsStats(testResultsResponse);
        setCurrentMonthResultsStats(currentMonthResultsResponse);
        setTestSetStats(testSetStatsResponse);
      } catch (err) {
        console.error('Error fetching KPIs:', err);
      } finally {
        setLoading(false);
        onLoadComplete?.();
      }
    };

    if (sessionToken) {
      fetchKPIs();
    }
  }, [sessionToken]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Calculate metrics
  const totalTests = testStats?.total || 0;
  const totalTestSets = testSetStats?.total || 0;

  // Get current month's pass rate and counts (latest data from 2-month query)
  const currentMonthData =
    currentMonthResultsStats?.timeline?.[
      currentMonthResultsStats.timeline.length - 1
    ]?.overall;
  const currentMonthPassRate = currentMonthData?.pass_rate || 0;
  const currentMonthPassed = currentMonthData?.passed || 0;
  const currentMonthFailed = currentMonthData?.failed || 0;

  // Get last month's pass rate for trend calculation
  const lastMonthPassRate =
    currentMonthResultsStats?.timeline?.[
      currentMonthResultsStats.timeline.length - 2
    ]?.overall?.pass_rate || 0;

  // Calculate month-over-month trend
  const passRateTrend =
    lastMonthPassRate > 0 ? currentMonthPassRate - lastMonthPassRate : 0;

  const passRateTrendFormatted =
    passRateTrend > 0
      ? `+${passRateTrend.toFixed(1)}%`
      : passRateTrend < 0
        ? `${passRateTrend.toFixed(1)}%`
        : '—';

  // Calculate test trend from history
  const testMonthlyData = testStats?.history?.monthly_counts || {};
  const testMonthKeys = Object.keys(testMonthlyData).slice(-6);
  const testTrend = testMonthKeys.map(key => testMonthlyData[key]);

  // Format month labels (e.g., "2024-01" -> "Jan")
  const testMonthLabels = testMonthKeys.map(monthKey => {
    const date = new Date(monthKey + '-01');
    return date.toLocaleDateString('en-US', { month: 'short' });
  });

  // Calculate cumulative tests for sparkline
  const cumulativeTests: number[] = [];
  let cumulative = 0;
  testTrend.forEach(count => {
    cumulative += count;
    cumulativeTests.push(cumulative);
  });

  // Get test execution counts from timeline
  const executionTimeline = testResultsStats?.timeline?.slice(-6) || [];
  const executionCounts = executionTimeline.map(
    item => item.overall?.total || 0
  );

  // Format month labels for executions (using 'date' field)
  const executionMonthLabels = executionTimeline.map(item => {
    if (item.date) {
      const date = new Date(item.date + '-01');
      return date.toLocaleDateString('en-US', { month: 'short' });
    }
    return '';
  });

  // Calculate recent test runs count (from last month)
  const recentTestRuns = executionCounts[executionCounts.length - 1] || 0;

  // Calculate test set trend
  const testSetMonthlyData = testSetStats?.history?.monthly_counts || {};
  const testSetMonthKeys = Object.keys(testSetMonthlyData).slice(-6);
  const testSetTrend = testSetMonthKeys.map(key => testSetMonthlyData[key]);

  // Format month labels for test sets
  const testSetMonthLabels = testSetMonthKeys.map(monthKey => {
    const date = new Date(monthKey + '-01');
    return date.toLocaleDateString('en-US', { month: 'short' });
  });

  const cumulativeTestSets: number[] = [];
  let cumulativeSets = 0;
  testSetTrend.forEach(count => {
    cumulativeSets += count;
    cumulativeTestSets.push(cumulativeSets);
  });

  // Calculate coverage percentage (tests per test set)
  const coveragePercentage =
    totalTestSets > 0
      ? Math.min(100, Math.round((totalTests / (totalTestSets * 10)) * 100))
      : 0;

  // Helper function to get pass rate display properties based on percentage
  const getPassRateDisplay = (passRate: number) => {
    if (passRate >= 80) {
      return {
        icon: CheckCircleIcon,
        color: theme.palette.success.main,
        bgColor: alpha(theme.palette.success.main, 0.1),
      };
    } else if (passRate >= 50) {
      return {
        icon: WarningIcon,
        color: theme.palette.warning.main,
        bgColor: alpha(theme.palette.warning.main, 0.1),
      };
    } else {
      return {
        icon: CancelIcon,
        color: theme.palette.error.main,
        bgColor: alpha(theme.palette.error.main, 0.1),
      };
    }
  };

  const passRateDisplay = getPassRateDisplay(currentMonthPassRate);

  return (
    <Box sx={{ mb: theme.spacing(4) }}>
      <Grid container spacing={theme.spacing(3)}>
        {/* This Month's Pass Rate */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card
            elevation={2}
            sx={{
              height: '100%',
              minHeight: theme.spacing(32),
              display: 'flex',
              flexDirection: 'column',
              position: 'relative',
              overflow: 'visible',
              transition: theme.transitions.create('box-shadow', {
                duration: theme.transitions.duration.short,
              }),
              '&:hover': {
                boxShadow: theme.shadows[8],
              },
            }}
          >
            <CardContent
              sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  mb: theme.spacing(2),
                }}
              >
                <Box
                  sx={{
                    backgroundColor: passRateDisplay.bgColor,
                    borderRadius: theme.shape.borderRadius,
                    p: theme.spacing(1),
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mr: theme.spacing(2),
                    color: passRateDisplay.color,
                    fontSize: theme.typography.h4.fontSize,
                  }}
                >
                  {React.createElement(passRateDisplay.icon)}
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      fontWeight: theme.typography.fontWeightMedium,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    Overall Pass Rate
                  </Typography>
                  <Typography
                    variant="h4"
                    sx={{
                      fontWeight: theme.typography.fontWeightBold,
                      mt: theme.spacing(0.5),
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {currentMonthPassRate.toFixed(1)}%
                  </Typography>
                </Box>
              </Box>

              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mb: theme.spacing(1) }}
              >
                Current performance
              </Typography>

              <Box
                sx={{
                  height: theme.spacing(7.5),
                  mt: theme.spacing(1),
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: theme.spacing(1),
                }}
              >
                <Tooltip
                  title={
                    <Box>
                      <Typography
                        variant="caption"
                        sx={{
                          display: 'block',
                          fontWeight: theme.typography.fontWeightMedium,
                        }}
                      >
                        Pass Rate: {currentMonthPassRate.toFixed(1)}%
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          display: 'block',
                          fontWeight: theme.typography.fontWeightMedium,
                        }}
                      >
                        Fail Rate: {(100 - currentMonthPassRate).toFixed(1)}%
                      </Typography>
                    </Box>
                  }
                  arrow
                  placement="top"
                  componentsProps={{
                    tooltip: {
                      sx: {
                        bgcolor: theme.palette.background.paper,
                        color: theme.palette.text.primary,
                        border: `1px solid ${theme.palette.divider}`,
                        borderRadius: theme.shape.borderRadius,
                        boxShadow: theme.shadows[2],
                        '& .MuiTooltip-arrow': {
                          color: theme.palette.background.paper,
                          '&::before': {
                            border: `1px solid ${theme.palette.divider}`,
                          },
                        },
                      },
                    },
                  }}
                >
                  <Box sx={{ display: 'inline-flex', cursor: 'pointer' }}>
                    <Gauge
                      value={currentMonthPassRate}
                      valueMin={0}
                      valueMax={100}
                      width={Number(theme.spacing(7.5).replace('px', ''))}
                      height={Number(theme.spacing(7.5).replace('px', ''))}
                      text={() => ''}
                      sx={{
                        [`& .MuiGauge-valueArc`]: {
                          fill: passRateDisplay.color,
                        },
                      }}
                    />
                  </Box>
                </Tooltip>

                {/* Legend */}
                <Box
                  sx={{
                    display: 'flex',
                    gap: theme.spacing(2),
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: theme.spacing(0.5),
                    }}
                  >
                    <Box
                      sx={{
                        width: theme.spacing(1),
                        height: theme.spacing(1),
                        borderRadius: '50%',
                        bgcolor: theme.palette.success.main,
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: theme.typography.fontWeightMedium,
                        color: theme.palette.success.main,
                      }}
                    >
                      {currentMonthPassed.toLocaleString()} Pass
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: theme.spacing(0.5),
                    }}
                  >
                    <Box
                      sx={{
                        width: theme.spacing(1),
                        height: theme.spacing(1),
                        borderRadius: '50%',
                        bgcolor: theme.palette.error.main,
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: theme.typography.fontWeightMedium,
                        color: theme.palette.error.main,
                      }}
                    >
                      {currentMonthFailed.toLocaleString()} Fail
                    </Typography>
                  </Box>
                </Box>
              </Box>

              {passRateTrend !== 0 && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    mt: theme.spacing(1),
                    color:
                      passRateTrend > 0
                        ? theme.palette.success.main
                        : theme.palette.error.main,
                  }}
                >
                  {passRateTrend > 0 ? (
                    <TrendingUpIcon
                      sx={{
                        fontSize: theme.typography.body2.fontSize,
                        mr: theme.spacing(0.5),
                      }}
                    />
                  ) : (
                    <TrendingDownIcon
                      sx={{
                        fontSize: theme.typography.body2.fontSize,
                        mr: theme.spacing(0.5),
                      }}
                    />
                  )}
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: theme.typography.fontWeightSemiBold }}
                  >
                    {passRateTrendFormatted} this month
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Test Executions */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KPICard
            title="Test Executions"
            value={recentTestRuns.toLocaleString()}
            icon={<PlayArrowIcon />}
            color={theme.palette.info.main}
            sparklineData={
              executionCounts.length > 0 ? executionCounts : undefined
            }
            sparklineLabels={
              executionMonthLabels.length > 0 ? executionMonthLabels : undefined
            }
            trend={
              executionCounts.length >= 2 &&
              executionCounts[executionCounts.length - 1] >
                executionCounts[executionCounts.length - 2]
                ? 'up'
                : executionCounts.length >= 2 &&
                    executionCounts[executionCounts.length - 1] <
                      executionCounts[executionCounts.length - 2]
                  ? 'down'
                  : 'neutral'
            }
            trendValue={
              executionCounts.length >= 2
                ? `${executionCounts[executionCounts.length - 1] > executionCounts[executionCounts.length - 2] ? '+' : ''}${executionCounts[executionCounts.length - 1] - executionCounts[executionCounts.length - 2]} from last month`
                : 'Last month'
            }
            subtitle="Tests executed"
          />
        </Grid>

        {/* Total Test Sets */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KPICard
            title="Test Sets"
            value={totalTestSets.toLocaleString()}
            icon={<HorizontalSplitIcon />}
            color={theme.palette.secondary.main}
            sparklineData={
              cumulativeTestSets.length > 0 ? cumulativeTestSets : undefined
            }
            sparklineLabels={
              testSetMonthLabels.length > 0 ? testSetMonthLabels : undefined
            }
            trend={
              cumulativeTestSets.length >= 2 &&
              cumulativeTestSets[cumulativeTestSets.length - 1] >
                cumulativeTestSets[cumulativeTestSets.length - 2]
                ? 'up'
                : 'neutral'
            }
            trendValue={
              testSetTrend.length > 0
                ? `+${testSetTrend[testTrend.length - 1]} this month`
                : undefined
            }
            subtitle="Test set collections"
          />
        </Grid>

        {/* Total Tests */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KPICard
            title="Tests"
            value={totalTests.toLocaleString()}
            icon={<ScienceIcon />}
            color={theme.palette.primary.main}
            sparklineData={
              cumulativeTests.length > 0 ? cumulativeTests : undefined
            }
            sparklineLabels={
              testMonthLabels.length > 0 ? testMonthLabels : undefined
            }
            trend={
              cumulativeTests.length >= 2 &&
              cumulativeTests[cumulativeTests.length - 1] >
                cumulativeTests[cumulativeTests.length - 2]
                ? 'up'
                : 'neutral'
            }
            trendValue={
              testTrend.length > 0
                ? `+${testTrend[testTrend.length - 1]} this month`
                : undefined
            }
            subtitle="Test cases managed"
          />
        </Grid>
      </Grid>
    </Box>
  );
}

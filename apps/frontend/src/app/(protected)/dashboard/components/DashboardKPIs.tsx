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
        position: 'relative',
        overflow: 'visible',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: theme.shadows[8],
        },
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2 }}>
          <Box
            sx={{
              backgroundColor: alpha(color, 0.1),
              borderRadius: 2,
              p: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mr: 2,
              color,
              fontSize: 28,
            }}
          >
            {icon}
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ fontWeight: 500 }}
            >
              {title}
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
              {value}
            </Typography>
          </Box>
        </Box>

        {subtitle && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: 1 }}
          >
            {subtitle}
          </Typography>
        )}

        {sparklineData && sparklineData.length > 0 && (
          <Box sx={{ height: 60, mt: 1 }}>
            <SparkLineChart
              data={sparklineData}
              height={60}
              showTooltip
              showHighlight
              color={color}
              curve="natural"
              area
              valueFormatter={value => value?.toLocaleString() || '0'}
              sx={{
                '& .MuiAreaElement-root': {
                  fill: color,
                  fillOpacity: 0.3,
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
              mt: 1,
              color:
                trend === 'up'
                  ? theme.palette.success.main
                  : trend === 'down'
                    ? theme.palette.error.main
                    : theme.palette.text.secondary,
            }}
          >
            {trend === 'up' ? (
              <TrendingUpIcon sx={{ fontSize: 16, mr: 0.5 }} />
            ) : trend === 'down' ? (
              <TrendingDownIcon sx={{ fontSize: 16, mr: 0.5 }} />
            ) : null}
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
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

  // Get current month's pass rate (latest data from 2-month query)
  const currentMonthPassRate =
    currentMonthResultsStats?.timeline?.[
      currentMonthResultsStats.timeline.length - 1
    ]?.overall?.pass_rate || 0;

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

  return (
    <Box sx={{ mb: 4 }}>
      <Grid container spacing={3}>
        {/* This Month's Pass Rate */}
        <Grid item xs={12} sm={6} md={3}>
          <Card
            elevation={2}
            sx={{
              height: '100%',
              transition: 'transform 0.2s, box-shadow 0.2s',
              '&:hover': {
                transform: 'translateY(-4px)',
                boxShadow: theme.shadows[8],
              },
            }}
          >
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
                <Box
                  sx={{
                    backgroundColor: alpha(theme.palette.success.main, 0.1),
                    borderRadius: 2,
                    p: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mr: 2,
                  }}
                >
                  <CheckCircleIcon
                    sx={{ color: theme.palette.success.main, fontSize: 28 }}
                  />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ fontWeight: 500 }}
                  >
                    Overall Pass Rate
                  </Typography>
                </Box>
              </Box>

              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  height: 100,
                  cursor: 'pointer',
                  '&:hover': {
                    opacity: 0.8,
                  },
                }}
                onClick={() => router.push('/test-results')}
              >
                <Gauge
                  value={currentMonthPassRate}
                  valueMin={0}
                  valueMax={100}
                  width={100}
                  height={100}
                  text={({ value }) => `${value?.toFixed(1)}%`}
                  sx={{
                    [`& .MuiGauge-valueArc`]: {
                      fill:
                        currentMonthPassRate > 60
                          ? theme.palette.success.main
                          : currentMonthPassRate >= 30
                            ? theme.palette.warning.main
                            : theme.palette.error.main,
                    },
                  }}
                />
              </Box>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mt: 1,
                  gap: 0.5,
                }}
              >
                {passRateTrend !== 0 && (
                  <>
                    {passRateTrend > 0 ? (
                      <TrendingUpIcon
                        sx={{
                          fontSize: 16,
                          color: theme.palette.success.main,
                        }}
                      />
                    ) : (
                      <TrendingDownIcon
                        sx={{
                          fontSize: 16,
                          color: theme.palette.error.main,
                        }}
                      />
                    )}
                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: 600,
                        color:
                          passRateTrend > 0
                            ? theme.palette.success.main
                            : theme.palette.error.main,
                      }}
                    >
                      {passRateTrendFormatted}
                    </Typography>
                  </>
                )}
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontWeight: 600 }}
                >
                  this month
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Test Executions */}
        <Grid item xs={12} sm={6} md={3}>
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
        <Grid item xs={12} sm={6} md={3}>
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
                ? `+${testSetTrend[testSetTrend.length - 1]} this month`
                : undefined
            }
            subtitle="Test set collections"
          />
        </Grid>

        {/* Total Tests */}
        <Grid item xs={12} sm={6} md={3}>
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

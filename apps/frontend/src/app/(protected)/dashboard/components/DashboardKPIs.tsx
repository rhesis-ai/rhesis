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
}

interface KPICardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  sparklineData?: number[];
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
          <Box sx={{ height: 40, mt: 1 }}>
            <SparkLineChart
              data={sparklineData}
              height={40}
              showTooltip
              showHighlight
              color={color}
              curve="natural"
              area
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

export default function DashboardKPIs({ sessionToken }: DashboardKPIsProps) {
  const theme = useTheme();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [testStats, setTestStats] = useState<TestStats | null>(null);
  const [testResultsStats, setTestResultsStats] =
    useState<TestResultsStats | null>(null);
  const [testSetStats, setTestSetStats] = useState<TestSetStatsResponse | null>(
    null
  );

  useEffect(() => {
    const fetchKPIs = async () => {
      try {
        setLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);

        const [testStatsResponse, testResultsResponse, testSetStatsResponse] =
          await Promise.all([
            clientFactory.getTestsClient().getTestStats({ top: 5, months: 6 }),
            clientFactory
              .getTestResultsClient()
              .getComprehensiveTestResultsStats({
                mode: 'timeline',
                months: 6,
              }),
            clientFactory.getTestSetsClient().getTestSetStats({ months: 6 }),
          ]);

        setTestStats(testStatsResponse);
        setTestResultsStats(testResultsResponse);
        setTestSetStats(testSetStatsResponse);
      } catch (err) {
        console.error('Error fetching KPIs:', err);
      } finally {
        setLoading(false);
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

  // Get pass rate from latest timeline data
  const latestPassRate =
    testResultsStats?.timeline?.[testResultsStats.timeline.length - 1]?.overall
      ?.pass_rate || 0;

  // Calculate test trend from history
  const testTrend = testStats?.history?.monthly_counts
    ? Object.values(testStats.history.monthly_counts).slice(-6)
    : [];

  // Calculate cumulative tests for sparkline
  const cumulativeTests: number[] = [];
  let cumulative = 0;
  testTrend.forEach(count => {
    cumulative += count;
    cumulativeTests.push(cumulative);
  });

  // Get test execution counts from timeline
  const executionCounts =
    testResultsStats?.timeline
      ?.map(item => item.overall?.total || 0)
      .slice(-6) || [];

  // Calculate recent test runs count (from last month)
  const recentTestRuns = executionCounts[executionCounts.length - 1] || 0;

  // Calculate test set trend
  const testSetTrend = testSetStats?.history?.monthly_counts
    ? Object.values(testSetStats.history.monthly_counts).slice(-6)
    : [];

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
        {/* Overall Quality Score */}
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
                    Quality Score
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
                  value={latestPassRate}
                  valueMin={0}
                  valueMax={100}
                  width={100}
                  height={100}
                  text={({ value }) => `${value?.toFixed(0)}%`}
                  sx={{
                    [`& .MuiGauge-valueArc`]: {
                      fill:
                        latestPassRate > 60
                          ? theme.palette.success.main
                          : latestPassRate >= 30
                            ? theme.palette.warning.main
                            : theme.palette.error.main,
                    },
                  }}
                />
              </Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', textAlign: 'center', mt: 1 }}
              >
                Pass Rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Total Tests */}
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Total Tests"
            value={totalTests.toLocaleString()}
            icon={<ScienceIcon />}
            color={theme.palette.primary.main}
            sparklineData={
              cumulativeTests.length > 0 ? cumulativeTests : undefined
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

        {/* Active Test Sets */}
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Test Sets"
            value={totalTestSets.toLocaleString()}
            icon={<HorizontalSplitIcon />}
            color={theme.palette.secondary.main}
            sparklineData={
              cumulativeTestSets.length > 0 ? cumulativeTestSets : undefined
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

        {/* Recent Test Runs */}
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Test Executions"
            value={recentTestRuns.toLocaleString()}
            icon={<PlayArrowIcon />}
            color={theme.palette.info.main}
            sparklineData={
              executionCounts.length > 0 ? executionCounts : undefined
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
      </Grid>
    </Box>
  );
}

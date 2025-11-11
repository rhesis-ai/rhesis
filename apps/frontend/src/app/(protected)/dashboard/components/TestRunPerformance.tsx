'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
  Chip,
  LinearProgress,
  Avatar,
  Tooltip,
  Paper,
  Button,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TestResultsStats,
  TestRunSummaryItem,
} from '@/utils/api-client/interfaces/test-results';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PersonIcon from '@mui/icons-material/Person';
import { formatDistanceToNow, parseISO } from 'date-fns';

interface TestRunPerformanceProps {
  sessionToken: string;
  onLoadComplete?: () => void;
}

const getStatusColor = (
  status?: string,
  taskState?: string
): 'success' | 'error' | 'warning' | 'info' | 'default' => {
  if (status?.toLowerCase().includes('completed')) return 'success';
  if (status?.toLowerCase().includes('failed')) return 'error';
  if (taskState === 'SUCCESS') return 'success';
  if (taskState === 'FAILURE') return 'error';
  if (taskState === 'PROGRESS') return 'info';
  if (taskState === 'PENDING') return 'warning';
  return 'default';
};

const getStatusIcon = (status?: string, taskState?: string) => {
  const color = getStatusColor(status, taskState);
  if (color === 'success') return <CheckCircleIcon fontSize="small" />;
  if (color === 'error') return <ErrorIcon fontSize="small" />;
  return <PlayArrowIcon fontSize="small" />;
};

const calculatePassRate = (testRun: TestRunSummaryItem): number => {
  // Use backend-calculated pass_rate with 1 decimal precision
  if (testRun.overall?.pass_rate != null) {
    return Math.round(testRun.overall.pass_rate * 10) / 10;
  }
  // Return -1 to indicate no data available
  return -1;
};

export default function TestRunPerformance({
  sessionToken,
  onLoadComplete,
}: TestRunPerformanceProps) {
  const router = useRouter();
  const [testRuns, setTestRuns] = useState<TestRunSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewportHeight, setViewportHeight] = useState(0);

  // Calculate how many test runs can fit based on viewport height
  // Each card is approximately 180px tall in 2-column grid, plus spacing
  // Account for dashboard header (~64px), KPIs (~200px), margins (~100px)
  const calculateLimit = useCallback(() => {
    if (viewportHeight === 0) return 6; // Default
    const availableHeight = viewportHeight - 364; // Header + KPIs + margins
    const cardHeight = 180; // Approximate height per card row (2 cards side-by-side)
    const calculatedLimit = Math.floor(availableHeight / cardHeight) * 2; // *2 for 2-column grid
    return Math.max(6, Math.min(calculatedLimit, 20)); // Min 6, max 20
  }, [viewportHeight]);

  const fetchTestRuns = useCallback(async () => {
    try {
      setLoading(true);
      const apiFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = apiFactory.getTestResultsClient();

      const options: TestResultsStatsOptions = {
        mode: 'test_runs',
        months: 6,
      };

      const response =
        await testResultsClient.getComprehensiveTestResultsStats(options);

      const limit = calculateLimit();

      // Sort by created_at (most recent first) and take calculated limit
      const sortedRuns = (response.test_run_summary || [])
        .filter(run => run.created_at)
        .sort((a, b) => {
          const dateA = new Date(a.created_at!).getTime();
          const dateB = new Date(b.created_at!).getTime();
          return dateB - dateA;
        })
        .slice(0, limit);

      setTestRuns(sortedRuns);
      setError(null);
    } catch (err) {
      setError('Unable to load test run data');
      setTestRuns([]);
    } finally {
      setLoading(false);
      onLoadComplete?.();
    }
  }, [sessionToken, calculateLimit]);

  useEffect(() => {
    // Set initial viewport height
    setViewportHeight(window.innerHeight);

    // Track viewport height changes
    const handleResize = () => {
      setViewportHeight(window.innerHeight);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (viewportHeight > 0) {
      fetchTestRuns();
    }
  }, [fetchTestRuns, viewportHeight]);

  const handleCardClick = (testRunId: string) => {
    router.push(`/test-runs/${testRunId}`);
  };

  const handleViewAll = () => {
    router.push('/test-runs');
  };

  // Calculate dynamic container height
  const containerHeight =
    calculateLimit() > 6
      ? `${Math.min(calculateLimit() * 90 + 150, viewportHeight - 364)}px`
      : '700px';

  if (loading) {
    return (
      <Paper sx={{ p: 3, height: containerHeight, overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3, height: containerHeight, overflow: 'auto' }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2.5,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <PlayArrowIcon color="primary" />
          <Typography variant="h6">Recent Test Runs</Typography>
        </Box>
        <Button size="small" onClick={handleViewAll}>
          View All
        </Button>
      </Box>

      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {testRuns.length === 0 ? (
          <Grid item xs={12}>
            <Typography color="text.secondary" align="center">
              No test runs found
            </Typography>
          </Grid>
        ) : (
          testRuns.map(testRun => {
            // Test runs in summary are completed - show pass/fail based on pass rate
            const passRate = calculatePassRate(testRun);
            const status = passRate >= 60 ? 'Completed' : 'Failed';
            const statusColor = passRate >= 60 ? 'success' : 'error';
            const statusIcon =
              passRate >= 60 ? (
                <CheckCircleIcon fontSize="small" />
              ) : (
                <ErrorIcon fontSize="small" />
              );
            const testSetName = testRun.name || 'Unknown Test Run';
            const startedAt = testRun.started_at
              ? formatDistanceToNow(parseISO(testRun.started_at), {
                  addSuffix: true,
                }).replace('about ', '~')
              : testRun.created_at
                ? formatDistanceToNow(parseISO(testRun.created_at), {
                    addSuffix: true,
                  }).replace('about ', '~')
                : 'N/A';

            // Get test count for display
            const totalTests =
              testRun.overall?.total || testRun.total_tests || 0;

            return (
              <Grid item xs={12} sm={6} md={6} key={testRun.id}>
                <Card
                  elevation={1}
                  sx={{
                    height: '100%',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    borderLeft: 4,
                    borderLeftColor:
                      statusColor === 'success'
                        ? 'success.main'
                        : statusColor === 'error'
                          ? 'error.main'
                          : statusColor === 'warning'
                            ? 'warning.main'
                            : 'info.main',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: 4,
                    },
                  }}
                  onClick={() => handleCardClick(testRun.id)}
                >
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    {/* Status Badge */}
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        mb: 1.5,
                      }}
                    >
                      <Chip
                        icon={statusIcon}
                        label={status}
                        color={statusColor}
                        size="small"
                      />
                      <Tooltip title={startedAt}>
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5,
                          }}
                        >
                          <ScheduleIcon fontSize="small" color="action" />
                          <Typography variant="caption" color="text.secondary">
                            {startedAt}
                          </Typography>
                        </Box>
                      </Tooltip>
                    </Box>

                    {/* Test Set Name */}
                    <Tooltip title={testSetName}>
                      <Typography
                        variant="subtitle2"
                        sx={{
                          fontWeight: 600,
                          mb: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {testSetName}
                      </Typography>
                    </Tooltip>

                    {/* Pass Rate Progress Bar */}
                    {passRate >= 0 && (
                      <Box sx={{ mb: 1.5 }}>
                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            mb: 0.5,
                          }}
                        >
                          <Typography variant="caption" color="text.secondary">
                            Pass Rate
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              fontWeight: 600,
                              color:
                                passRate >= 80
                                  ? 'success.main'
                                  : passRate >= 60
                                    ? 'warning.main'
                                    : 'error.main',
                            }}
                          >
                            {passRate.toFixed(1)}%
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={passRate}
                          color={
                            passRate >= 80
                              ? 'success'
                              : passRate >= 60
                                ? 'warning'
                                : 'error'
                          }
                          sx={{ height: 6, borderRadius: 1 }}
                        />
                      </Box>
                    )}

                    {/* Test Count */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {totalTests} test{totalTests !== 1 ? 's' : ''}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            );
          })
        )}
      </Grid>
    </Paper>
  );
}

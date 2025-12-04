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
  useTheme,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

// Extended interface to include stats
interface TestRunWithStats extends TestRunDetail {
  stats?: {
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
  } | null;
}
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PersonIcon from '@mui/icons-material/Person';
import { CategoryIcon } from '@/components/icons';
import { formatDistanceToNow, parseISO } from 'date-fns';
import Link from 'next/link';

interface TestRunPerformanceProps {
  sessionToken: string;
  onLoadComplete?: () => void;
  limit?: number;
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

const calculatePassRate = (testRun: TestRunWithStats): number => {
  // Use stats from API if available
  if (testRun.stats?.pass_rate != null) {
    return Math.round(testRun.stats.pass_rate * 10) / 10;
  }
  // Return -1 to indicate no data available
  return -1;
};

export default function TestRunPerformance({
  sessionToken,
  onLoadComplete,
  limit: propLimit,
}: TestRunPerformanceProps) {
  const theme = useTheme();
  const router = useRouter();
  const [testRuns, setTestRuns] = useState<TestRunWithStats[]>([]);
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
      const testRunsClient = apiFactory.getTestRunsClient();
      const testResultsClient = apiFactory.getTestResultsClient();

      const limit = propLimit ?? calculateLimit();

      // Fetch test runs with proper details including test_set
      const response = await testRunsClient.getTestRuns({
        skip: 0,
        limit: limit,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      // Fetch statistics for each test run
      const testRunsWithStats = await Promise.all(
        response.data.map(async testRun => {
          try {
            // Fetch test results stats for this specific test run
            const stats =
              await testResultsClient.getComprehensiveTestResultsStats({
                mode: 'summary',
                test_run_ids: [testRun.id],
              });

            // Add stats to the test run object
            return {
              ...testRun,
              stats: stats.overall_pass_rates || null,
            };
          } catch (error) {
            // If stats fetch fails, return test run without stats
            console.error(
              `Failed to fetch stats for test run ${testRun.id}:`,
              error
            );
            return {
              ...testRun,
              stats: null,
            };
          }
        })
      );

      setTestRuns(testRunsWithStats);
      setError(null);
    } catch (err) {
      setError('Unable to load test run data');
      setTestRuns([]);
    } finally {
      setLoading(false);
      onLoadComplete?.();
    }
  }, [sessionToken, calculateLimit, propLimit]);

  useEffect(() => {
    // Set viewport height once on mount
    setViewportHeight(window.innerHeight);
  }, []);

  useEffect(() => {
    // Fetch data once viewport height is set
    if (sessionToken && viewportHeight > 0) {
      fetchTestRuns();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, viewportHeight]); // Fetch when sessionToken changes or when viewport height is initially set

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
      : theme.spacing(87.5);

  if (loading) {
    return (
      <Paper
        sx={{
          p: theme.spacing(3),
          height: containerHeight,
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            p: theme.spacing(3),
          }}
        >
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  return (
    <Paper
      sx={{ p: theme.spacing(3), height: containerHeight, overflow: 'auto' }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: theme.spacing(2.5),
        }}
      >
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: theme.spacing(1) }}
        >
          <PlayArrowIcon color="primary" />
          <Typography variant="h6">Recent Test Runs</Typography>
        </Box>
        <Button size="small" onClick={handleViewAll}>
          View All
        </Button>
      </Box>

      {error && (
        <Alert severity="warning" sx={{ mb: theme.spacing(2) }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={theme.spacing(2)}>
        {testRuns.length === 0 ? (
          <Grid size={{ xs: 12 }}>
            <Typography color="text.secondary" align="center">
              No test runs
            </Typography>
          </Grid>
        ) : (
          testRuns.map(testRun => {
            // Get status from the test run
            const statusName = testRun.status?.name || 'Unknown';
            const taskState = testRun.attributes?.task_state;
            const statusColor = getStatusColor(statusName, taskState);
            const statusIcon = getStatusIcon(statusName, taskState);

            // Get pass rate
            const passRate = calculatePassRate(testRun);

            // Get test run name
            const testRunName = testRun.name || 'Unnamed Test Run';

            // Get test set information
            const testSet = testRun.test_configuration?.test_set;
            const testSetName = testSet?.name || 'Unknown Test Set';
            const testSetId = testSet?.id;
            const testSetType = testSet?.test_set_type?.type_value;

            // Get timing information
            const startedAt = (() => {
              const parseDate = (dateStr: string) => {
                try {
                  const parsedDate = parseISO(dateStr);

                  // Validate the parsed date
                  if (isNaN(parsedDate.getTime())) {
                    return null;
                  }

                  return formatDistanceToNow(parsedDate, {
                    addSuffix: true,
                  }).replace('about ', '~');
                } catch (error) {
                  return null;
                }
              };

              // Try started_at from attributes first (most accurate for execution time)
              if (
                testRun.attributes?.started_at &&
                typeof testRun.attributes.started_at === 'string'
              ) {
                const result = parseDate(testRun.attributes.started_at);
                if (result) return result;
              }

              // Fall back to created_at
              if (
                testRun.created_at &&
                typeof testRun.created_at === 'string'
              ) {
                const result = parseDate(testRun.created_at);
                if (result) return result;
              }

              return 'N/A';
            })();

            // Get test count and pass/fail counts from stats
            const totalTests = testRun.stats?.total || 0;
            const passedTests = testRun.stats?.passed || 0;
            const failedTests = testRun.stats?.failed || 0;

            return (
              <Grid size={{ xs: 12 }} key={testRun.id}>
                <Card
                  elevation={1}
                  sx={{
                    height: '100%',
                    minHeight: theme.spacing(21),
                    cursor: 'pointer',
                    transition: theme.transitions.create('box-shadow', {
                      duration: theme.transitions.duration.short,
                    }),
                    borderLeft: theme.spacing(0.5),
                    borderLeftColor:
                      statusColor === 'success'
                        ? 'success.main'
                        : statusColor === 'error'
                          ? 'error.main'
                          : statusColor === 'warning'
                            ? 'warning.main'
                            : 'info.main',
                    '&:hover': {
                      boxShadow: theme.shadows[4],
                    },
                  }}
                  onClick={() => handleCardClick(testRun.id)}
                >
                  <CardContent
                    sx={{
                      p: theme.spacing(2),
                      '&:last-child': { pb: theme.spacing(2) },
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                    }}
                  >
                    {/* Top Section: Header Information */}
                    <Box>
                      {/* Status Badge and Test Run Name */}
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          mb: theme.spacing(1.5),
                        }}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: theme.spacing(1),
                            flex: 1,
                            minWidth: 0,
                          }}
                        >
                          <Chip
                            icon={statusIcon}
                            label={statusName}
                            color={statusColor}
                            size="small"
                          />
                          <Tooltip title={testRunName}>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{
                                fontWeight: theme.typography.fontWeightMedium,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {testRunName}
                            </Typography>
                          </Tooltip>
                        </Box>
                        <Tooltip title={startedAt}>
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: theme.spacing(0.5),
                              flexShrink: 0,
                            }}
                          >
                            <ScheduleIcon fontSize="small" color="action" />
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {startedAt}
                            </Typography>
                          </Box>
                        </Tooltip>
                      </Box>

                      {/* Test Set Link */}
                      {testSetId && (
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: theme.spacing(0.5),
                          }}
                          onClick={e => e.stopPropagation()}
                        >
                          <CategoryIcon fontSize="small" color="action" />
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: theme.spacing(1),
                              minWidth: 0,
                              flex: 1,
                            }}
                          >
                            <Link
                              href={`/test-sets/${testSetId}`}
                              style={{
                                textDecoration: 'none',
                                minWidth: 0,
                                flex: 1,
                              }}
                            >
                              <Typography
                                variant="caption"
                                color="primary"
                                sx={{
                                  fontWeight: theme.typography.fontWeightMedium,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                  '&:hover': {
                                    textDecoration: 'underline',
                                  },
                                }}
                              >
                                {testSetName}
                              </Typography>
                            </Link>
                            {testSetType && (
                              <Chip
                                label={testSetType}
                                size="small"
                                variant="outlined"
                                sx={{
                                  height: theme.spacing(2.5),
                                  fontSize: theme.typography.caption.fontSize,
                                  fontWeight: theme.typography.fontWeightMedium,
                                  '& .MuiChip-label': {
                                    px: theme.spacing(0.75),
                                  },
                                }}
                              />
                            )}
                          </Box>
                        </Box>
                      )}
                    </Box>

                    {/* Bottom Section: Performance Metrics */}
                    <Box>
                      {/* Pass Rate Progress Bar */}
                      {passRate >= 0 && (
                        <Box sx={{ mb: theme.spacing(1.5) }}>
                          <Box
                            sx={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              mb: theme.spacing(0.5),
                            }}
                          >
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Pass Rate
                            </Typography>
                            <Typography
                              variant="caption"
                              sx={{
                                fontWeight: theme.typography.fontWeightMedium,
                                color:
                                  passRate > 75
                                    ? 'success.main'
                                    : passRate >= 50
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
                              passRate > 75
                                ? 'success'
                                : passRate >= 50
                                  ? 'warning'
                                  : 'error'
                            }
                            sx={{
                              height: theme.spacing(0.75),
                              borderRadius: theme.shape.borderRadius,
                            }}
                          />
                        </Box>
                      )}

                      {/* Test Count with Pass/Fail breakdown */}
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: theme.spacing(1),
                          flexWrap: 'wrap',
                        }}
                      >
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ fontWeight: theme.typography.fontWeightMedium }}
                        >
                          {totalTests} test{totalTests !== 1 ? 's' : ''}
                        </Typography>
                        {totalTests > 0 && (
                          <>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              •
                            </Typography>
                            <Typography
                              variant="caption"
                              sx={{
                                color: 'success.main',
                                fontWeight: theme.typography.fontWeightMedium,
                              }}
                            >
                              {passedTests} passed
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              •
                            </Typography>
                            <Typography
                              variant="caption"
                              sx={{
                                color: 'error.main',
                                fontWeight: theme.typography.fontWeightMedium,
                              }}
                            >
                              {failedTests} failed
                            </Typography>
                          </>
                        )}
                      </Box>
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

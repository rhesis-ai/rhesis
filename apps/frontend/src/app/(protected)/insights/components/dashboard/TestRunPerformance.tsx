'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
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
  Tooltip,
  Paper,
  Button,
  useTheme,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TestRunSummaryItem } from '@/utils/api-client/interfaces/test-results';

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
import ScheduleIcon from '@mui/icons-material/Schedule';
import { CategoryIcon } from '@/components/icons';
import { formatDistanceToNow, parseISO } from 'date-fns';
import Link from 'next/link';
import {
  getTestRunStatusColor,
  getTestRunStatusIcon,
} from '@/components/common/TestRunStatus';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import { BORDER_RADIUS, ELEVATION, GREYSCALE } from '@/styles/theme';

interface TestRunPerformanceProps {
  sessionToken: string;
  filters?: Partial<TestResultsStatsOptions>;
  searchValue?: string;
  onLoadComplete?: () => void;
  limit?: number;
}

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
  filters = {},
  searchValue = '',
  onLoadComplete,
  limit: propLimit,
}: TestRunPerformanceProps) {
  const theme = useTheme();
  const router = useRouter();
  const [testRuns, setTestRuns] = useState<TestRunWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Calculate how many test runs can fit based on viewport height
  // Each card is approximately 180px tall in 2-column grid, plus spacing
  // Account for dashboard header (~64px), KPIs (~200px), margins (~100px)
  const calculateLimit = useCallback(() => {
    if (typeof window === 'undefined') return 6; // Default for SSR
    const vh = window.innerHeight;
    const availableHeight = vh - 364; // Header + KPIs + margins
    const cardHeight = 180; // Approximate height per card row (2 cards side-by-side)
    const calculatedLimit = Math.floor(availableHeight / cardHeight) * 2; // *2 for 2-column grid
    return Math.max(6, Math.min(calculatedLimit, 20)); // Min 6, max 20
  }, []);

  const fetchTestRuns = useCallback(async () => {
    try {
      setLoading(true);
      const apiFactory = new ApiClientFactory(sessionToken);
      const testRunsClient = apiFactory.getTestRunsClient();
      const testResultsClient = apiFactory.getTestResultsClient();

      const limit = propLimit ?? calculateLimit();

      const testSetId = filters.test_set_ids?.[0];
      const response = await testRunsClient.getTestRuns({
        skip: 0,
        limit: limit,
        sort_by: 'created_at',
        sort_order: 'desc',
        ...(testSetId
          ? {
              filter: `test_configuration/test_set/id eq '${testSetId}'`,
            }
          : {}),
      });

      if (response.data.length === 0) {
        setTestRuns([]);
        setError(null);
        return;
      }

      const testRunIds = response.data.map(run => run.id);

      // Fetch statistics for all test runs in a single call
      try {
        const statsResponse =
          await testResultsClient.getComprehensiveTestResultsStats({
            mode: 'test_runs',
            test_run_ids: testRunIds,
          });

        // Map stats back to test runs
        const statsMap = new Map(
          (statsResponse.test_run_summary || []).map(
            (summary: TestRunSummaryItem) => [summary.id, summary.overall]
          )
        );

        const testRunsWithStats = response.data.map(testRun => ({
          ...testRun,
          stats: statsMap.get(testRun.id) || null,
        }));

        let runs = testRunsWithStats;
        if (searchValue.trim()) {
          const query = searchValue.trim().toLowerCase();
          runs = runs.filter(run => {
            const name = run.name?.toLowerCase() ?? '';
            const testSetName =
              run.test_configuration?.test_set?.name?.toLowerCase() ?? '';
            return name.includes(query) || testSetName.includes(query);
          });
        }
        setTestRuns(runs);
      } catch (error) {
        console.error('Failed to fetch test run stats:', error);
        let runs = response.data.map(run => ({ ...run, stats: null }));
        if (searchValue.trim()) {
          const query = searchValue.trim().toLowerCase();
          runs = runs.filter(run => {
            const name = run.name?.toLowerCase() ?? '';
            const testSetName =
              run.test_configuration?.test_set?.name?.toLowerCase() ?? '';
            return name.includes(query) || testSetName.includes(query);
          });
        }
        setTestRuns(runs);
      }

      setError(null);
    } catch (_err) {
      setError('Unable to load test run data');
      setTestRuns([]);
    } finally {
      setLoading(false);
      onLoadComplete?.();
    }
  }, [
    sessionToken,
    calculateLimit,
    propLimit,
    onLoadComplete,
    filters.test_set_ids,
    searchValue,
  ]);

  useEffect(() => {
    if (sessionToken) {
      fetchTestRuns();
    }
  }, [sessionToken, fetchTestRuns]);

  const handleCardClick = (testRunId: string) => {
    router.push(`/test-runs/${testRunId}`);
  };

  const handleViewAll = () => {
    router.push('/test-runs');
  };

  // Stable height on SSR/hydration when embedded with a fixed limit (e.g. insights)
  const containerHeight = useMemo(() => {
    if (propLimit != null) {
      return theme.spacing(87.5);
    }
    if (typeof window === 'undefined') {
      return theme.spacing(87.5);
    }
    const calculated = calculateLimit();
    if (calculated > 6) {
      return `${Math.min(calculated * 90 + 150, window.innerHeight - 364)}px`;
    }
    return theme.spacing(87.5);
  }, [propLimit, theme, calculateLimit]);

  const paperSx = {
    p: theme.spacing(3),
    height: containerHeight,
    borderRadius: BORDER_RADIUS.md,
    border: `1px solid ${
      theme.palette.mode === 'light'
        ? GREYSCALE.light.border
        : theme.palette.divider
    }`,
    boxShadow: ELEVATION.xs,
  };

  if (loading) {
    return (
      <Paper
        elevation={0}
        sx={{
          ...paperSx,
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
    <Paper elevation={0} sx={{ ...paperSx, overflow: 'auto' }}>
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
            const statusColor = getTestRunStatusColor(statusName);
            const statusIcon = getTestRunStatusIcon(statusName);

            // Get pass rate
            const passRate = calculatePassRate(testRun);

            // Get test run name
            const testRunName = testRun.name || 'Unnamed Test Run';

            // Get test set information
            const testSet = testRun.test_configuration?.test_set;
            const testSetName = testSet?.name || 'Unknown Test Set';
            const testSetId = testSet?.id;
            const testSetType = testSet?.test_set_type?.type_value;
            // Get total number of tests in the test set (not executed tests)
            const totalTestsInSet =
              testSet?.attributes?.metadata?.total_tests ?? null;

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
                } catch (_error) {
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
            // Use total tests in test set (not executed tests) for display
            const totalTests = totalTestsInSet ?? testRun.stats?.total ?? 0;
            const passedTests = testRun.stats?.passed || 0;
            const failedTests = testRun.stats?.failed || 0;

            return (
              <Grid size={{ xs: 12 }} key={testRun.id}>
                <Card
                  elevation={0}
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

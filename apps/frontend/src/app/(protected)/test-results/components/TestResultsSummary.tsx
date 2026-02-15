'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  Alert,
  CircularProgress,
  useTheme,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Warning as WarningIcon,
  Assessment as AssessmentIcon,
  Analytics as AnalyticsIcon,
} from '@mui/icons-material';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import { TestResultsClient } from '@/utils/api-client/test-results-client';
import { TestResultsStats } from '@/utils/api-client/interfaces/test-results';

interface TestResultsSummaryProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
  searchValue?: string;
}

// Helper function to get pass rate display properties based on percentage
function getPassRateDisplay(passRate: number) {
  if (passRate >= 80) {
    return {
      icon: CheckCircleIcon,
      color: 'success.main' as const,
      iconColor: 'success' as const,
      stage: 'good',
    };
  } else if (passRate >= 50) {
    return {
      icon: WarningIcon,
      color: 'warning.main' as const,
      iconColor: 'warning' as const,
      stage: 'medium',
    };
  } else {
    return {
      icon: CancelIcon,
      color: 'error.main' as const,
      iconColor: 'error' as const,
      stage: 'poor',
    };
  }
}

export default function TestResultsSummary({
  sessionToken,
  filters,
  searchValue = '',
}: TestResultsSummaryProps) {
  const theme = useTheme();
  const [data, setData] = useState<TestResultsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSummaryData = async () => {
      setLoading(true);
      setError(null);

      try {
        const client = new TestResultsClient(sessionToken);
        const result = await client.getComprehensiveTestResultsStats({
          ...filters,
          mode: 'all', // Use 'all' mode to get both summary and metadata
        });

        setData(result);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to fetch summary data'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchSummaryData();
  }, [sessionToken, filters]);

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: theme.customSpacing.section.small }}>
        {error}
      </Alert>
    );
  }

  if (!data) {
    return (
      <Alert severity="info" sx={{ mt: theme.customSpacing.section.small }}>
        No summary data available.
      </Alert>
    );
  }

  const { test_run_summary, metadata } = data;

  // Calculate overall statistics from test run summaries
  const totalTests =
    test_run_summary?.reduce((sum, run) => sum + (run.total_tests || 0), 0) ||
    0;
  const totalPassed =
    test_run_summary?.reduce(
      (sum, run) => sum + (run.overall?.passed || 0),
      0
    ) || 0;
  const totalFailed =
    test_run_summary?.reduce(
      (sum, run) => sum + (run.overall?.failed || 0),
      0
    ) || 0;
  const overallPassRate = totalTests > 0 ? (totalPassed / totalTests) * 100 : 0;

  // Get display properties for pass rate
  const passRateDisplay = getPassRateDisplay(overallPassRate);

  // Get all test runs within the date range
  const recentTestRuns =
    test_run_summary && test_run_summary.length > 0
      ? test_run_summary
          .filter(
            (run): run is typeof run & { created_at: string } =>
              !!run.created_at
          )
          .sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime()
          )
      : [];

  // Filter test runs based on search value
  const filteredTestRuns = recentTestRuns.filter(run => {
    if (!searchValue) return true;
    const searchLower = searchValue.toLowerCase();
    const runName = (run.name || '').toLowerCase();
    const runDate = run.created_at
      ? new Date(run.created_at).toLocaleString().toLowerCase()
      : '';
    return runName.includes(searchLower) || runDate.includes(searchLower);
  });

  return (
    <Box>
      {/* Overall Statistics Cards */}
      <Grid
        container
        spacing={theme.customSpacing.section.medium}
        sx={{ mb: theme.customSpacing.section.medium }}
      >
        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <Card
            elevation={theme.elevation.standard}
            sx={{ height: '100%', minHeight: 120 }}
          >
            <CardContent
              sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                p: theme.customSpacing.container.medium,
              }}
            >
              <Box
                display="flex"
                alignItems="center"
                gap={theme.customSpacing.container.small}
              >
                <AnalyticsIcon
                  color="primary"
                  sx={{ fontSize: theme.iconSizes.large }}
                />
                <Box>
                  <Typography variant="h4" fontWeight="bold">
                    {metadata.total_test_runs}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Test Runs
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <Card
            elevation={theme.elevation.standard}
            sx={{ height: '100%', minHeight: 120 }}
          >
            <CardContent
              sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                p: theme.customSpacing.container.medium,
              }}
            >
              <Box
                display="flex"
                alignItems="center"
                gap={theme.customSpacing.container.small}
              >
                <AssessmentIcon
                  color="primary"
                  sx={{ fontSize: theme.iconSizes.large }}
                />
                <Box>
                  <Typography variant="h4" fontWeight="bold">
                    {metadata.total_test_results}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Test Results
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <Card
            elevation={theme.elevation.standard}
            sx={{ height: '100%', minHeight: 120 }}
          >
            <CardContent
              sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                p: theme.customSpacing.container.medium,
              }}
            >
              <Box
                display="flex"
                alignItems="center"
                gap={theme.customSpacing.container.small}
              >
                {React.createElement(passRateDisplay.icon, {
                  color: passRateDisplay.iconColor,
                  sx: { fontSize: theme.iconSizes.large },
                })}
                <Box>
                  <Typography
                    variant="h4"
                    fontWeight="bold"
                    color={passRateDisplay.color}
                  >
                    {overallPassRate.toFixed(1)}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Overall Pass Rate
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid
          size={{
            xs: 12,
            sm: 6,
            md: 3,
          }}
        >
          <Card
            elevation={theme.elevation.standard}
            sx={{ height: '100%', minHeight: 120 }}
          >
            <CardContent
              sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                p: theme.customSpacing.container.medium,
              }}
            >
              <Box
                display="flex"
                alignItems="center"
                gap={theme.customSpacing.container.small}
              >
                <CancelIcon
                  color="error"
                  sx={{ fontSize: theme.iconSizes.large }}
                />
                <Box>
                  <Typography variant="h4" fontWeight="bold" color="error.main">
                    {totalFailed}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Failed Tests
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
      {/* Recent Test Runs */}
      {recentTestRuns.length > 0 && (
        <Paper
          elevation={theme.elevation.standard}
          sx={{
            p: theme.customSpacing.container.medium,
            mb: theme.customSpacing.section.medium,
          }}
        >
          <Typography variant="h6" gutterBottom>
            Test Runs ({filteredTestRuns.length}
            {searchValue && recentTestRuns.length !== filteredTestRuns.length
              ? ` of ${recentTestRuns.length}`
              : ''}
            )
          </Typography>
          {filteredTestRuns.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
              No test runs match your search.
            </Typography>
          ) : (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: theme.customSpacing.section.small,
              }}
            >
              {filteredTestRuns.map((run, index) => (
                <Box
                  key={run.id || index}
                  sx={{
                    p: theme.customSpacing.container.small,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: theme => theme.shape.borderRadius * 0.25,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease-in-out',
                    '&:hover': {
                      backgroundColor: 'action.hover',
                      borderColor: 'primary.main',
                      transform: 'translateY(-1px)',
                      boxShadow: theme.shadows[2],
                    },
                  }}
                  onClick={() => {
                    if (run.id) {
                      window.open(`/test-runs/${run.id}`, '_blank');
                    }
                  }}
                >
                  <Box
                    display="flex"
                    alignItems="center"
                    gap={theme.customSpacing.container.small}
                    mb={1}
                  >
                    <Chip
                      label={run.name || `Run ${index + 1}`}
                      variant="outlined"
                      size="small"
                    />
                    <Typography variant="body2" color="text.secondary">
                      {run.created_at
                        ? new Date(run.created_at).toLocaleString()
                        : 'N/A'}
                    </Typography>
                  </Box>
                  <Grid container spacing={theme.customSpacing.container.small}>
                    <Grid
                      size={{
                        xs: 6,
                        sm: 3,
                      }}
                    >
                      <Typography variant="caption" color="text.secondary">
                        Total Tests
                      </Typography>
                      <Typography variant="body1" fontWeight="medium">
                        {run.total_tests || 0}
                      </Typography>
                    </Grid>
                    <Grid
                      size={{
                        xs: 6,
                        sm: 3,
                      }}
                    >
                      <Typography variant="caption" color="text.secondary">
                        Passed
                      </Typography>
                      <Typography
                        variant="body1"
                        fontWeight="medium"
                        color="success.main"
                      >
                        {run.overall?.passed || 0}
                      </Typography>
                    </Grid>
                    <Grid
                      size={{
                        xs: 6,
                        sm: 3,
                      }}
                    >
                      <Typography variant="caption" color="text.secondary">
                        Failed
                      </Typography>
                      <Typography
                        variant="body1"
                        fontWeight="medium"
                        color="error.main"
                      >
                        {run.overall?.failed || 0}
                      </Typography>
                    </Grid>
                    <Grid
                      size={{
                        xs: 6,
                        sm: 3,
                      }}
                    >
                      <Typography variant="caption" color="text.secondary">
                        Pass Rate
                      </Typography>
                      <Typography variant="body1" fontWeight="medium">
                        {run.overall?.pass_rate?.toFixed(1) || '0.0'}%
                      </Typography>
                    </Grid>
                  </Grid>
                </Box>
              ))}
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}

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
  CircularProgress
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Warning as WarningIcon,
  Assessment as AssessmentIcon,
  Schedule as ScheduleIcon,
  Analytics as AnalyticsIcon
} from '@mui/icons-material';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import { TestResultsClient } from '@/utils/api-client/test-results-client';
import { TestResultsStats, TestRunSummaryItem } from '@/utils/api-client/interfaces/test-results';

interface TestResultsSummaryProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
}

// Helper function to get pass rate display properties based on percentage
function getPassRateDisplay(passRate: number) {
  if (passRate >= 80) {
    return {
      icon: CheckCircleIcon,
      color: 'success.main' as const,
      iconColor: 'success' as const,
      stage: 'good'
    };
  } else if (passRate >= 50) {
    return {
      icon: WarningIcon,
      color: 'warning.main' as const,
      iconColor: 'warning' as const,
      stage: 'medium'
    };
  } else {
    return {
      icon: CancelIcon,
      color: 'error.main' as const,
      iconColor: 'error' as const,
      stage: 'poor'
    };
  }
}

export default function TestResultsSummary({ sessionToken, filters }: TestResultsSummaryProps) {
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
          mode: 'all' // Use 'all' mode to get both summary and metadata
        });
        
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch summary data');
      } finally {
        setLoading(false);
      }
    };

    fetchSummaryData();
  }, [sessionToken, filters]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!data) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        No summary data available.
      </Alert>
    );
  }

  const { test_run_summary, metadata } = data;

  // Calculate overall statistics from test run summaries
  const totalTests = test_run_summary?.reduce((sum, run) => sum + (run.total_tests || 0), 0) || 0;
  const totalPassed = test_run_summary?.reduce((sum, run) => sum + (run.overall?.passed || 0), 0) || 0;
  const totalFailed = test_run_summary?.reduce((sum, run) => sum + (run.overall?.failed || 0), 0) || 0;
  const overallPassRate = totalTests > 0 ? (totalPassed / totalTests) * 100 : 0;
  
  // Get display properties for pass rate
  const passRateDisplay = getPassRateDisplay(overallPassRate);

  // Get the 5 most recent test runs
  const recentTestRuns = test_run_summary && test_run_summary.length > 0 
    ? test_run_summary
        .filter(run => run.created_at) // Filter out runs without created_at
        .sort((a, b) => new Date(b.created_at!).getTime() - new Date(a.created_at!).getTime())
        .slice(0, 5) // Take the 5 most recent
    : [];

  return (
    <Box>
      {/* Overall Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%', minHeight: 120 }}>
            <CardContent sx={{ height: '100%', display: 'flex', alignItems: 'center' }}>
              <Box display="flex" alignItems="center" gap={2}>
                <AnalyticsIcon color="primary" />
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

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%', minHeight: 120 }}>
            <CardContent sx={{ height: '100%', display: 'flex', alignItems: 'center' }}>
              <Box display="flex" alignItems="center" gap={2}>
                <AssessmentIcon color="primary" />
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

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%', minHeight: 120 }}>
            <CardContent sx={{ height: '100%', display: 'flex', alignItems: 'center' }}>
              <Box display="flex" alignItems="center" gap={2}>
                {React.createElement(passRateDisplay.icon, { color: passRateDisplay.iconColor })}
                <Box>
                  <Typography variant="h4" fontWeight="bold" color={passRateDisplay.color}>
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

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%', minHeight: 120 }}>
            <CardContent sx={{ height: '100%', display: 'flex', alignItems: 'center' }}>
              <Box display="flex" alignItems="center" gap={2}>
                <ScheduleIcon color="primary" />
                <Box>
                  <Typography variant="body1" fontWeight="bold">
                    {metadata.period || `Last ${filters.months || 6} months`}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Reporting Period
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Test Runs */}
      {recentTestRuns.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Latest Test Runs ({recentTestRuns.length})
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {recentTestRuns.map((run, index) => (
              <Box 
                key={run.id || index} 
                sx={{ 
                  p: 2, 
                  border: 1, 
                  borderColor: 'divider', 
                  borderRadius: 1
                }}
              >
                <Box display="flex" alignItems="center" gap={2} mb={1}>
                  <Chip 
                    label={run.name || `Run ${index + 1}`} 
                    color={index === 0 ? "primary" : "default"}
                    variant={index === 0 ? "filled" : "outlined"}
                    size="small"
                  />
                  <Typography variant="body2" color="text.secondary">
                    {run.created_at ? new Date(run.created_at).toLocaleString() : 'N/A'}
                  </Typography>
                  {index === 0 && (
                    <Chip label="Most Recent" size="small" color="success" variant="outlined" />
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">Total Tests</Typography>
                    <Typography variant="body1" fontWeight="medium">{run.total_tests || 0}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">Passed</Typography>
                    <Typography variant="body1" fontWeight="medium" color="success.main">{run.overall?.passed || 0}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">Failed</Typography>
                    <Typography variant="body1" fontWeight="medium" color="error.main">{run.overall?.failed || 0}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">Pass Rate</Typography>
                    <Typography variant="body1" fontWeight="medium">{run.overall?.pass_rate?.toFixed(1) || '0.0'}%</Typography>
                  </Grid>
                </Grid>
              </Box>
            ))}
          </Box>
        </Paper>
      )}






    </Box>
  );
}


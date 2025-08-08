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

  // Get the most recent test run
  const mostRecentRun = test_run_summary && test_run_summary.length > 0 
    ? test_run_summary
        .filter(run => run.created_at) // Filter out runs without created_at
        .sort((a, b) => new Date(b.created_at!).getTime() - new Date(a.created_at!).getTime())[0]
    : null;

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
                <CheckCircleIcon color="success" />
                <Box>
                  <Typography variant="h4" fontWeight="bold" color="success.main">
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

      {/* Most Recent Test Run */}
      {mostRecentRun && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Most Recent Test Run
          </Typography>
          <Box display="flex" alignItems="center" gap={2} mb={2}>
            <Chip 
              label={mostRecentRun.name} 
              color="primary" 
              variant="outlined"
            />
            <Typography variant="body2" color="text.secondary">
              {mostRecentRun.created_at ? new Date(mostRecentRun.created_at).toLocaleString() : 'N/A'}
            </Typography>
          </Box>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Total Tests</Typography>
              <Typography variant="h6">{mostRecentRun.total_tests || 0}</Typography>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Passed</Typography>
              <Typography variant="h6" color="success.main">{mostRecentRun.overall?.passed || 0}</Typography>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Failed</Typography>
              <Typography variant="h6" color="error.main">{mostRecentRun.overall?.failed || 0}</Typography>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Pass Rate</Typography>
              <Typography variant="h6">{mostRecentRun.overall?.pass_rate?.toFixed(1) || '0.0'}%</Typography>
            </Grid>
          </Grid>
        </Paper>
      )}






    </Box>
  );
}


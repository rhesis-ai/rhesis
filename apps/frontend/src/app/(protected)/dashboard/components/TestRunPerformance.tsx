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
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PersonIcon from '@mui/icons-material/Person';
import { formatDistanceToNow, parseISO } from 'date-fns';

interface TestRunPerformanceProps {
  sessionToken: string;
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

const calculatePassRate = (testRun: TestRunDetail): number => {
  // Check if attributes contain result data
  if (testRun.attributes) {
    const total =
      testRun.attributes.total_tests || testRun.attributes.test_count || 0;
    const passed =
      testRun.attributes.passed_tests || testRun.attributes.passed || 0;
    if (total > 0) {
      return Math.round((passed / total) * 100);
    }
  }
  // Return -1 to indicate no data available
  return -1;
};

export default function TestRunPerformance({
  sessionToken,
}: TestRunPerformanceProps) {
  const router = useRouter();
  const [testRuns, setTestRuns] = useState<TestRunDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTestRuns = useCallback(async () => {
    try {
      setLoading(true);
      const apiFactory = new ApiClientFactory(sessionToken);
      const testRunsClient = apiFactory.getTestRunsClient();

      const response = await testRunsClient.getTestRuns({
        skip: 0,
        limit: 6,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      setTestRuns(response.data);
      setError(null);
    } catch (err) {
      setError('Unable to load test run data');
      setTestRuns([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken]);

  useEffect(() => {
    fetchTestRuns();
  }, [fetchTestRuns]);

  const handleCardClick = (testRunId: string) => {
    router.push(`/test-runs/${testRunId}`);
  };

  const handleViewAll = () => {
    router.push('/test-runs');
  };

  if (loading) {
    return (
      <Paper
        sx={{ p: 3, height: '500px', maxHeight: '500px', overflow: 'hidden' }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3, height: '500px', maxHeight: '500px', overflow: 'auto' }}>
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
            const status =
              testRun.status?.name || testRun.attributes?.task_state;
            const statusColor = getStatusColor(
              testRun.status?.name,
              testRun.attributes?.task_state
            );
            const statusIcon = getStatusIcon(
              testRun.status?.name,
              testRun.attributes?.task_state
            );
            const passRate = calculatePassRate(testRun);
            const testSetName =
              testRun.test_configuration?.test_set?.name || 'Unknown Test Set';
            const executor = testRun.user
              ? `${testRun.user.given_name || ''} ${testRun.user.family_name || ''}`.trim() ||
                testRun.user.email
              : 'Unknown';
            const startedAt = testRun.attributes?.started_at
              ? formatDistanceToNow(parseISO(testRun.attributes.started_at), {
                  addSuffix: true,
                })
              : 'N/A';

            return (
              <Grid item xs={12} sm={6} md={4} key={testRun.id}>
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
                            {passRate}%
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

                    {/* Executor */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Avatar
                        sx={{ width: 22, height: 22, bgcolor: 'primary.main' }}
                      >
                        <PersonIcon sx={{ fontSize: 15 }} />
                      </Avatar>
                      <Tooltip title={executor}>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {executor}
                        </Typography>
                      </Tooltip>
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

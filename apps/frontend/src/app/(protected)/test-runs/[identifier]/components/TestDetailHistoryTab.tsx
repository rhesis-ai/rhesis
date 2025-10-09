'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  useTheme,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import Link from 'next/link';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { formatDate } from '@/utils/date';

interface TestDetailHistoryTabProps {
  test: TestResultDetail;
  testRunId: string;
  sessionToken: string;
}

interface HistoricalResult {
  id: string;
  testRunId: string;
  testRunName: string;
  passed: boolean;
  passedMetrics: number;
  totalMetrics: number;
  executedAt: string;
}

export default function TestDetailHistoryTab({
  test,
  testRunId,
  sessionToken,
}: TestDetailHistoryTabProps) {
  const theme = useTheme();
  const [history, setHistory] = useState<HistoricalResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchHistory() {
      if (!test.test_id) {
        setError('No test ID available');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const testResultsClient = clientFactory.getTestResultsClient();

        // Fetch historical test results for this test
        const results = await testResultsClient.getTestResults({
          filter: `test_id eq '${test.test_id}'`,
          limit: 10,
          skip: 0,
        });

        // Get unique test run IDs to fetch their names
        const testRunIds = [
          ...new Set(
            results.data.filter(r => r.test_run_id).map(r => r.test_run_id!)
          ),
        ];

        // Fetch test run details to get actual names
        const testRunsClient = clientFactory.getTestRunsClient();
        const testRunsData = await Promise.allSettled(
          testRunIds.map(id => testRunsClient.getTestRun(id))
        );

        // Create a map of test run IDs to names
        const testRunNamesMap = new Map<string, string>();
        testRunsData.forEach((result, index) => {
          if (result.status === 'fulfilled') {
            const testRun = result.value;
            // Use name if available, otherwise use the test run ID
            const displayName = testRun.name || testRunIds[index];
            testRunNamesMap.set(testRun.id, displayName);
            console.log(
              `Mapped test run ${testRun.id} to name: ${displayName}`
            );
          } else {
            // If fetch failed, use the ID as fallback
            console.warn(
              `Failed to fetch test run ${testRunIds[index]}:`,
              result.reason
            );
            testRunNamesMap.set(testRunIds[index], testRunIds[index]);
          }
        });

        // Process results into historical format
        const historicalData: HistoricalResult[] = results.data.map(result => {
          const metrics = result.test_metrics?.metrics || {};
          const metricValues = Object.values(metrics);
          const passedMetrics = metricValues.filter(
            m => m.is_successful
          ).length;
          const totalMetrics = metricValues.length;
          const passed = totalMetrics > 0 && passedMetrics === totalMetrics;

          return {
            id: result.id,
            testRunId: result.test_run_id || 'unknown',
            testRunName: result.test_run_id
              ? testRunNamesMap.get(result.test_run_id) || result.test_run_id
              : 'unknown',
            passed,
            passedMetrics,
            totalMetrics,
            executedAt: result.created_at || new Date().toISOString(),
          };
        });

        // Sort by execution date (most recent first)
        historicalData.sort(
          (a, b) =>
            new Date(b.executedAt).getTime() - new Date(a.executedAt).getTime()
        );

        // Group by test run - only show one result per test run (the most recent one)
        const uniqueByTestRun = new Map<string, HistoricalResult>();
        historicalData.forEach(item => {
          if (!uniqueByTestRun.has(item.testRunId)) {
            uniqueByTestRun.set(item.testRunId, item);
          }
        });

        // Convert back to array and limit to 10
        const dedupedHistory = Array.from(uniqueByTestRun.values())
          .sort(
            (a, b) =>
              new Date(b.executedAt).getTime() -
              new Date(a.executedAt).getTime()
          )
          .slice(0, 10);

        setHistory(dedupedHistory);
        setError(null);
      } catch (err) {
        console.error('Error fetching test history:', err);
        setError('Failed to load test history');
      } finally {
        setLoading(false);
      }
    }

    fetchHistory();
  }, [test.test_id, sessionToken]);

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          p: 4,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        Test Execution History
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Last 10 test runs where this test was executed
      </Typography>

      {history.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            No historical data available for this test
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Status</TableCell>
                <TableCell>Test Run</TableCell>
                <TableCell>Metrics</TableCell>
                <TableCell>Executed At</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map(item => (
                <TableRow
                  key={item.id}
                  sx={{
                    backgroundColor:
                      item.testRunId === testRunId
                        ? theme.palette.action.selected
                        : 'transparent',
                    '&:hover': {
                      backgroundColor: theme.palette.action.hover,
                    },
                  }}
                >
                  <TableCell>
                    <Chip
                      icon={
                        item.passed ? (
                          <CheckCircleOutlineIcon />
                        ) : (
                          <CancelOutlinedIcon />
                        )
                      }
                      label={item.passed ? 'Pass' : 'Fail'}
                      size="small"
                      color={item.passed ? 'success' : 'error'}
                      sx={{ minWidth: 80 }}
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {item.testRunId !== 'unknown' ? (
                        <Link
                          href={`/test-runs/${item.testRunId}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ textDecoration: 'none' }}
                        >
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 0.5,
                              '&:hover': {
                                '& .test-run-name': {
                                  color: theme.palette.primary.main,
                                  textDecoration: 'underline',
                                },
                              },
                            }}
                          >
                            <Typography
                              variant="body2"
                              className="test-run-name"
                              sx={{
                                transition: 'color 0.2s',
                                color:
                                  item.testRunId === testRunId
                                    ? 'primary.main'
                                    : 'text.primary',
                                fontWeight:
                                  item.testRunId === testRunId ? 600 : 400,
                              }}
                            >
                              {item.testRunName}
                            </Typography>
                            <OpenInNewIcon
                              sx={{
                                fontSize: 14,
                                color: 'text.disabled',
                              }}
                            />
                          </Box>
                        </Link>
                      ) : (
                        <Typography variant="body2">
                          {item.testRunName}
                        </Typography>
                      )}
                      {item.testRunId === testRunId && (
                        <Chip label="Current" size="small" color="primary" />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {item.passedMetrics}/{item.totalMetrics} passed
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {formatDate(item.executedAt)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Summary Statistics */}
      {history.length > 0 && (
        <Box sx={{ mt: 3 }}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" fontWeight={600} gutterBottom>
              Summary Statistics
            </Typography>
            <Box sx={{ display: 'flex', gap: 4, mt: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Total Executions
                </Typography>
                <Typography variant="h6">{history.length}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Pass Rate
                </Typography>
                <Typography
                  variant="h6"
                  color={
                    history.filter(h => h.passed).length / history.length >= 0.8
                      ? 'success.main'
                      : 'error.main'
                  }
                >
                  {(
                    (history.filter(h => h.passed).length / history.length) *
                    100
                  ).toFixed(1)}
                  %
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Passed
                </Typography>
                <Typography variant="h6" color="success.main">
                  {history.filter(h => h.passed).length}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Failed
                </Typography>
                <Typography variant="h6" color="error.main">
                  {history.filter(h => !h.passed).length}
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Box>
      )}
    </Box>
  );
}

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
  Chip,
  CircularProgress,
  Alert,
  useTheme,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import Link from 'next/link';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { formatDate } from '@/utils/date';
import StatusChip from '@/components/common/StatusChip';

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
            results.data
              .filter(
                (r): r is typeof r & { test_run_id: string } => !!r.test_run_id
              )
              .map(r => r.test_run_id)
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
          } else {
            // If fetch failed, use the ID as fallback
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
      } catch (_err) {
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
      {/* Summary Statistics */}
      {history.length > 0 && (
        <Box sx={{ display: 'flex', gap: '26px', mb: 3 }}>
          {[
            {
              label: 'Total Executions',
              value: history.length,
              color: '#1a1c20',
            },
            {
              label: 'Pass Rate',
              value: `${((history.filter(h => h.passed).length / history.length) * 100).toFixed(1)}%`,
              color:
                history.filter(h => h.passed).length / history.length >= 0.8
                  ? '#38ad87'
                  : '#de3355',
            },
            {
              label: 'Passed',
              value: history.filter(h => h.passed).length,
              color: '#38ad87',
            },
            {
              label: 'Failed',
              value: history.filter(h => !h.passed).length,
              color: '#de3355',
            },
          ].map(stat => (
            <Box
              key={stat.label}
              sx={{
                flex: 1,
                bgcolor: '#f3f4f6',
                borderRadius: '10px',
                boxShadow: '0px 3px 5px rgba(0,0,0,0.09)',
                p: '30px',
                height: '140px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '18px',
                  color: '#1a1c20',
                }}
              >
                {stat.label}
              </Typography>
              <Typography
                sx={{
                  fontSize: 36,
                  fontWeight: 700,
                  lineHeight: 1,
                  color: stat.color,
                }}
              >
                {stat.value}
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      {history.length === 0 ? (
        <Box
          sx={{
            bgcolor: 'background.paper',
            borderRadius: '12px',
            border: '1px solid #cdd2da',
            boxShadow: '0px 2px 4px rgba(84,90,101,0.25)',
            p: 3,
            textAlign: 'center',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            No historical data available for this test
          </Typography>
        </Box>
      ) : (
        <Box
          sx={{
            bgcolor: 'background.paper',
            borderRadius: '12px',
            border: '1px solid #cdd2da',
            boxShadow: '0px 2px 4px rgba(84,90,101,0.25)',
            overflow: 'hidden',
          }}
        >
          <TableContainer>
            <Table
              sx={{
                '& .MuiTableCell-root': {
                  borderBottom: '1px solid #cdd2da',
                  fontSize: 14,
                  lineHeight: '22px',
                  py: '13px',
                  px: '12px',
                  backgroundColor: '#ffffff',
                },
                '& .MuiTableBody-root .MuiTableRow-root:last-child .MuiTableCell-root':
                  {
                    borderBottom: 'none',
                  },
                '& .MuiTableRow-root:hover .MuiTableCell-root': {
                  backgroundColor: '#f9fafb',
                },
              }}
            >
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
                    Status
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
                    Test Run
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
                    Metrics
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
                    Executed At
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {history.map(item => (
                  <TableRow
                    key={item.id}
                    sx={{
                      '&:hover .MuiTableCell-root': {
                        bgcolor: '#f9fafb',
                      },
                    }}
                  >
                    <TableCell>
                      <StatusChip
                        passed={item.passed}
                        label={item.passed ? 'Pass' : 'Fail'}
                        size="small"
                        variant="outlined"
                        sx={{
                          borderColor: item.passed ? '#38ad87' : '#de3355',
                          color: item.passed ? '#38ad87' : '#de3355',
                          '& .MuiChip-icon': { color: 'inherit' },
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        {item.testRunId !== 'unknown' ? (
                          <Link
                            href={`/test-runs/${item.testRunId}${test.test_id ? `?selectedresult=${test.test_id}` : ''}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ textDecoration: 'none' }}
                            onClick={() => {}}
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
                                className="test-run-name"
                                sx={{
                                  fontSize: 14,
                                  lineHeight: '22px',
                                  transition: 'color 0.2s',
                                  color: '#2a2e36',
                                  fontWeight:
                                    item.testRunId === testRunId ? 600 : 400,
                                }}
                              >
                                {item.testRunName}
                              </Typography>
                              <OpenInNewIcon
                                sx={{ fontSize: 14, color: 'text.disabled' }}
                              />
                            </Box>
                          </Link>
                        ) : (
                          <Typography
                            sx={{
                              fontSize: 14,
                              lineHeight: '22px',
                              color: '#2a2e36',
                            }}
                          >
                            {item.testRunName}
                          </Typography>
                        )}
                        {item.testRunId === testRunId && (
                          <Chip
                            label="Current"
                            size="small"
                            variant="outlined"
                            sx={{
                              borderColor: '#cdd2da',
                              color: '#2a2e36',
                              fontSize: 12,
                            }}
                          />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell sx={{ color: '#2a2e36' }}>
                      {item.passedMetrics}/{item.totalMetrics} passed
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>
                      {formatDate(item.executedAt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Box>
  );
}

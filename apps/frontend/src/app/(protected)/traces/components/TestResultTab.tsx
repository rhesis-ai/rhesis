'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Stack,
  useTheme,
  CircularProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableRow,
  TableCell,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import StatusChip from '@/components/common/StatusChip';
import { TraceDetailResponse } from '@/utils/api-client/interfaces/telemetry';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  getTestResultStatusWithReview,
  getTestResultLabelWithReview,
} from '@/utils/test-result-status';
import { format } from 'date-fns';

interface TestResultTabProps {
  trace: TraceDetailResponse;
  sessionToken: string;
}

export default function TestResultTab({
  trace,
  sessionToken,
}: TestResultTabProps) {
  const theme = useTheme();
  const [testResult, setTestResult] = useState<TestResultDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTestResult = useCallback(async () => {
    if (!trace.test_result?.id) return;

    setLoading(true);
    setError(null);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = apiFactory.getTestResultsClient();
      const result = await testResultsClient.getTestResult(
        trace.test_result.id
      );
      setTestResult(result);
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error
          ? err.message
          : 'Failed to fetch test result details';
      setError(errorMsg);
      console.error('Failed to fetch test result:', err);
    } finally {
      setLoading(false);
    }
  }, [trace.test_result?.id, sessionToken]);

  useEffect(() => {
    if (trace.test_result?.id) {
      fetchTestResult();
    }
  }, [trace.test_result?.id, fetchTestResult]);

  if (!trace.test_result) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="text.secondary">
          No test result data available
        </Typography>
      </Box>
    );
  }

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

  if (!testResult) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="text.secondary">Loading test result...</Typography>
      </Box>
    );
  }

  // Get test result status
  const testStatus = getTestResultStatusWithReview(testResult);
  const testLabel = getTestResultLabelWithReview(testResult);

  return (
    <Box sx={{ p: theme => theme.spacing(2) }}>
      {/* Overview Card - Rounded */}
      <Card
        variant="outlined"
        sx={{
          mb: theme => theme.spacing(2),
          backgroundColor: theme => theme.palette.success.main + '08',
          borderColor: theme => theme.palette.success.main + '20',
        }}
      >
        <CardContent>
          <Stack spacing={2}>
            {/* Status, Test Type, and Behavior - Side by Side */}
            <Box sx={{ display: 'flex', gap: theme => theme.spacing(2) }}>
              {/* Test Status Cell */}
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Test Status
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    mt: 0.5,
                  }}
                >
                  <StatusChip
                    status={testStatus}
                    label={testLabel}
                    size="medium"
                    variant="filled"
                    sx={{ fontWeight: 600 }}
                  />
                  {/* Show Review Confirmed indicator if review exists */}
                  {testResult.last_review && (
                    <Chip
                      icon={<CheckIcon sx={{ fontSize: 16 }} />}
                      label="Confirmed"
                      size="medium"
                      color="success"
                      variant="filled"
                      sx={{
                        fontWeight: 600,
                      }}
                    />
                  )}
                </Box>
              </Box>

              {/* Test Type Cell */}
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Test Type
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  <Chip
                    label={
                      testResult.test_output?.goal
                        ? 'Multi-turn'
                        : 'Single-turn'
                    }
                    size="medium"
                    variant="outlined"
                    color={
                      testResult.test_output?.goal ? 'primary' : 'secondary'
                    }
                  />
                </Box>
              </Box>

              {/* Test Behavior Cell */}
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Behavior
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  {testResult.test?.behavior?.name ? (
                    <Chip
                      label={testResult.test.behavior.name}
                      size="medium"
                      variant="outlined"
                      color="info"
                    />
                  ) : (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        fontSize: theme => theme.typography.body2.fontSize,
                      }}
                    >
                      No behavior
                    </Typography>
                  )}
                </Box>
              </Box>
            </Box>

            {/* Test Content - Prompt for single-turn, Goal for multi-turn */}
            {(() => {
              const goal =
                testResult.test_output?.goal ||
                testResult.test_output?.test_configuration?.goal;
              const prompt = testResult.test?.prompt?.content; // Access prompt from testResult.test relationship

              const content = goal || prompt;
              const contentType = goal ? 'Test Goal' : 'Test Prompt';

              if (content) {
                return (
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      {contentType}
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        mt: 0.5,
                        p: 1,
                        backgroundColor: theme =>
                          theme.palette.background.default,
                        borderRadius: theme => theme.shape.borderRadius * 0.25,
                        border: theme => `1px solid ${theme.palette.divider}`,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        maxHeight: 150,
                        overflow: 'auto',
                      }}
                    >
                      {content}
                    </Typography>
                  </Box>
                );
              }
              return null;
            })()}

            {/* Test Output - Right after test content */}
            {testResult.test_output?.output && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Test Output
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    mt: 0.5,
                    p: 1,
                    backgroundColor: theme => theme.palette.background.default,
                    borderRadius: theme => theme.shape.borderRadius * 0.25,
                    border: theme => `1px solid ${theme.palette.divider}`,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontFamily: 'monospace',
                    fontSize: theme => theme.typography.body2.fontSize,
                    maxHeight: 150,
                    overflow: 'auto',
                  }}
                >
                  {testResult.test_output.output}
                </Typography>
              </Box>
            )}

            {/* Multi-turn specific details */}
            {testResult.test_output?.goal && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Test Configuration
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                  {testResult.test_output.turns_used && (
                    <Chip
                      label={`${testResult.test_output.turns_used} turns used`}
                      size="small"
                      variant="outlined"
                    />
                  )}
                  {testResult.test_output.test_configuration?.max_turns && (
                    <Chip
                      label={`Max: ${testResult.test_output.test_configuration.max_turns} turns`}
                      size="small"
                      variant="outlined"
                    />
                  )}
                  {testResult.test_output.goal_achieved !== undefined && (
                    <Chip
                      label={
                        testResult.test_output.goal_achieved
                          ? 'Goal Achieved'
                          : 'Goal Not Achieved'
                      }
                      size="small"
                      color={
                        testResult.test_output.goal_achieved
                          ? 'success'
                          : 'error'
                      }
                      variant="outlined"
                    />
                  )}
                </Stack>
              </Box>
            )}

            {/* Timestamps */}
            {testResult.created_at && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Execution Time
                </Typography>
                <Typography variant="body2">
                  {format(new Date(testResult.created_at), 'PPpp')}
                </Typography>
              </Box>
            )}
          </Stack>
        </CardContent>
      </Card>

      {/* Metrics Summary - Rectangular Accordion */}
      {testResult.test_metrics?.metrics && (
        <Accordion
          defaultExpanded
          sx={{
            backgroundColor: theme => theme.palette.info.main + '08',
            borderColor: theme => theme.palette.info.main + '20',
            mb: 1,
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">
              Metrics ({Object.keys(testResult.test_metrics.metrics).length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Table size="small">
              <TableBody>
                {Object.entries(testResult.test_metrics.metrics).map(
                  ([name, metric]) => (
                    <TableRow key={name}>
                      <TableCell
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: theme => theme.typography.body2.fontSize,
                          width: '60%',
                        }}
                      >
                        {name}
                      </TableCell>
                      <TableCell sx={{ textAlign: 'right' }}>
                        <Chip
                          label={metric.is_successful ? 'Pass' : 'Fail'}
                          color={metric.is_successful ? 'success' : 'error'}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                    </TableRow>
                  )
                )}
              </TableBody>
            </Table>
          </AccordionDetails>
        </Accordion>
      )}

      {/* Review Comments - Rectangular Accordion */}
      {testResult.last_review?.comments && (
        <Accordion
          sx={{
            backgroundColor: theme => theme.palette.secondary.main + '08',
            borderColor: theme => theme.palette.secondary.main + '20',
            mb: 1,
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">Review Comments</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Card
              variant="outlined"
              sx={{
                backgroundColor: theme.palette.background.paper,
              }}
            >
              <CardContent>
                <Typography
                  variant="body2"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {testResult.last_review.comments}
                </Typography>
              </CardContent>
            </Card>
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}

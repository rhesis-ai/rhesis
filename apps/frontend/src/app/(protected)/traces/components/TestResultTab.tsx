'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  useTheme,
  CircularProgress,
  Alert,
} from '@mui/material';
import StatusChip from '@/components/common/StatusChip';
import { TraceDetailResponse } from '@/utils/api-client/interfaces/telemetry';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  DeletedEntityAlert,
  type DeletedEntityData,
} from '@/components/common/DeletedEntityAlert';
import {
  getDeletedEntityData,
  isDeletedEntityError,
} from '@/utils/entity-error-handler';
import {
  getEffectiveTestResultStatus,
  getTestResultLabel,
} from '@/utils/test-result-status';
import { format } from 'date-fns';

interface TestResultTabProps {
  trace: TraceDetailResponse;
  /** Off when the trace's own metrics are already shown above. */
  showMetrics?: boolean;
}

export default function TestResultTab({
  trace,
  showMetrics = true,
}: TestResultTabProps) {
  const theme = useTheme();
  const [testResult, setTestResult] = useState<TestResultDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletedTestResult, setDeletedTestResult] =
    useState<DeletedEntityData | null>(null);

  const fetchTestResult = useCallback(async () => {
    if (!trace.test_result?.id) return;

    setLoading(true);
    setError(null);
    setDeletedTestResult(null);
    setTestResult(null);

    try {
      const apiFactory = new ApiClientFactory();
      const testResultsClient = apiFactory.getTestResultsClient();
      const result = await testResultsClient.getTestResult(
        trace.test_result.id
      );
      setTestResult(result);
    } catch (err: unknown) {
      if (isDeletedEntityError(err)) {
        setDeletedTestResult(
          getDeletedEntityData(err) ?? {
            model_name: 'TestResult',
            model_name_display: 'Test Result',
            item_id: trace.test_result.id,
            table_name: 'test_result',
            restore_url: `/recycle/test_result/${trace.test_result.id}/restore`,
            message: 'The test for this trace no longer exists.',
          }
        );
      } else {
        const errorMsg =
          err instanceof Error
            ? err.message
            : 'Failed to fetch test result details';
        setError(errorMsg);
        console.error('Failed to fetch test result:', err);
      }
    } finally {
      setLoading(false);
    }
  }, [trace.test_result?.id]);

  useEffect(() => {
    if (trace.test_result?.id) {
      fetchTestResult();
    }
  }, [trace.test_result?.id, fetchTestResult]);

  if (!trace.test_result) {
    return (
      <Typography variant="caption" color="text.secondary">
        No test result data available
      </Typography>
    );
  }

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          p: 2,
        }}
      >
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (deletedTestResult) {
    return <DeletedEntityAlert entityData={deletedTestResult} />;
  }

  if (!testResult) {
    return (
      <Typography variant="caption" color="text.secondary">
        Loading test result...
      </Typography>
    );
  }

  const testStatus = getEffectiveTestResultStatus(testResult);
  const testLabel = getTestResultLabel(testResult);
  const goal =
    testResult.test_output?.goal ||
    testResult.test_output?.test_configuration?.goal;
  const prompt = testResult.test?.prompt?.content;
  const turnsUsed = testResult.test_output?.turns_used;
  const maxTurns = testResult.test_output?.test_configuration?.max_turns;
  const metrics = showMetrics ? testResult.test_metrics?.metrics : undefined;

  return (
    <Box>
      <Typography
        variant="caption"
        component="h3"
        sx={{
          fontWeight: 600,
          color: 'text.primary',
          display: 'flex',
          alignItems: 'center',
          minHeight: t => t.spacing(3.5),
          mb: 0.5,
        }}
      >
        Test
      </Typography>
      <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
        <Row label="Result">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <StatusChip
              status={testStatus}
              label={testLabel}
              size="small"
              variant="filled"
            />
            {testResult.last_annotation && (
              <Typography variant="caption" color="success.main">
                Confirmed
              </Typography>
            )}
          </Box>
        </Row>
        <Row label="Type">
          {trace.conversation_id ? 'Multi-turn' : 'Single-turn'}
          {turnsUsed
            ? ` · ${turnsUsed} turns used${maxTurns ? ` of ${maxTurns}` : ''}`
            : ''}
        </Row>
        {testResult.test?.requirement?.name && (
          <Row label="Requirement">{testResult.test.requirement.name}</Row>
        )}
        {(goal || prompt) && (
          <Row label={goal ? 'Goal' : 'Prompt'}>
            <Box component="span" sx={{ whiteSpace: 'pre-wrap' }}>
              {goal || prompt}
            </Box>
          </Row>
        )}
        {testResult.test_output?.output && (
          <Row label="Output">
            <Box
              component="span"
              sx={{
                fontFamily: theme.typography.fontFamilyCode,
                whiteSpace: 'pre-wrap',
                display: 'block',
                maxHeight: theme.spacing(18),
                overflow: 'auto',
              }}
            >
              {testResult.test_output.output}
            </Box>
          </Row>
        )}
        {testResult.created_at && (
          <Row label="Executed">
            {format(new Date(testResult.created_at), 'PPpp')}
          </Row>
        )}
        {metrics &&
          Object.entries(metrics).map(([name, metric]) => (
            <Row key={name} label={name}>
              <StatusChip
                passed={!!metric.is_successful}
                label={metric.is_successful ? 'Passed' : 'Failed'}
                size="small"
                variant="outlined"
              />
            </Row>
          ))}
        {testResult.last_annotation?.comments && (
          <Row label="Review">
            <Box component="span" sx={{ whiteSpace: 'pre-wrap' }}>
              {testResult.last_annotation.comments}
            </Box>
          </Row>
        )}
      </Box>
    </Box>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1.5,
        py: 0.75,
        px: 1,
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          width: t => t.spacing(13),
          flexShrink: 0,
          pt: 0.25,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {label}
      </Typography>
      <Typography
        variant="body2"
        component="div"
        sx={{ flex: 1, minWidth: 0, wordBreak: 'break-word' }}
      >
        {children}
      </Typography>
    </Box>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { TraceDetailResponse } from '@/utils/api-client/interfaces/telemetry';
import {
  TestResultDetail,
  ConversationTurn,
  GoalEvaluation,
} from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ConversationHistory from '@/components/common/ConversationHistory';

interface ConversationTraceViewProps {
  trace: TraceDetailResponse;
  sessionToken: string;
}

export default function ConversationTraceView({
  trace,
  sessionToken,
}: ConversationTraceViewProps) {
  const [testResult, setTestResult] = useState<TestResultDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTestResult = async () => {
      if (!trace.test_result?.id) {
        setLoading(false);
        return;
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const client = clientFactory.getTestResultsClient();
        const result = await client.getTestResult(trace.test_result.id);
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
    };

    fetchTestResult();
  }, [trace.test_result?.id, sessionToken]);

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100%',
          p: 4,
        }}
      >
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error" variant="body2">
          {error}
        </Typography>
      </Box>
    );
  }

  const conversationSummary: ConversationTurn[] =
    testResult?.test_output?.conversation_summary || [];
  const goalEvaluation: GoalEvaluation | undefined =
    testResult?.test_output?.goal_evaluation;

  if (conversationSummary.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary" variant="body2">
          No conversation data available for this trace
        </Typography>
      </Box>
    );
  }

  return (
    <ConversationHistory
      conversationSummary={conversationSummary}
      goalEvaluation={goalEvaluation}
      project={trace.project}
      maxHeight="100%"
    />
  );
}

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
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import ConversationHistory from '@/components/common/ConversationHistory';

interface ConversationTraceViewProps {
  trace: TraceDetailResponse;
  sessionToken: string;
  onSpanSelect?: (span: SpanNode) => void;
  rootSpans?: SpanNode[];
}

/**
 * Reconstruct conversation turns from span attributes when no test result
 * is available (e.g. direct SDK/endpoint multi-turn invocations).
 */
function reconstructConversationFromSpans(
  rootSpans: SpanNode[]
): ConversationTurn[] {
  return rootSpans
    .filter(
      span =>
        span.attributes['rhesis.conversation.input'] ||
        span.attributes['rhesis.conversation.output']
    )
    .map((span, i) => ({
      turn: i + 1,
      timestamp: span.start_time,
      penelope_message: String(
        span.attributes['rhesis.conversation.input'] || ''
      ),
      target_response: String(
        span.attributes['rhesis.conversation.output'] || ''
      ),
      penelope_reasoning: '',
      session_id: span.span_id,
      success: span.status_code !== 'ERROR',
    }));
}

export default function ConversationTraceView({
  trace,
  sessionToken,
  onSpanSelect,
  rootSpans,
}: ConversationTraceViewProps) {
  const [testResult, setTestResult] = useState<TestResultDetail | null>(null);
  const [loading, setLoading] = useState(!!trace.test_result?.id);
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

  // Path A: test-result-based conversation (with goal evaluation)
  const conversationSummary: ConversationTurn[] =
    testResult?.test_output?.conversation_summary || [];
  const goalEvaluation: GoalEvaluation | undefined =
    testResult?.test_output?.goal_evaluation;

  // Path B: span-based reconstruction (no test result)
  const spanConversation =
    conversationSummary.length === 0 && rootSpans
      ? reconstructConversationFromSpans(rootSpans)
      : [];

  const turns =
    conversationSummary.length > 0 ? conversationSummary : spanConversation;

  const handleResponseClick = (turnNumber: number) => {
    if (onSpanSelect && rootSpans) {
      const spanIndex = turnNumber - 1;
      if (spanIndex >= 0 && spanIndex < rootSpans.length) {
        onSpanSelect(rootSpans[spanIndex]);
      }
    }
  };

  if (turns.length === 0) {
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
      conversationSummary={turns}
      goalEvaluation={
        conversationSummary.length > 0 ? goalEvaluation : undefined
      }
      project={trace.project}
      onResponseClick={
        onSpanSelect && rootSpans ? handleResponseClick : undefined
      }
      maxHeight="100%"
    />
  );
}

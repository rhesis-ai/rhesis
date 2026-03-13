'use client';

import { useState, useEffect } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import {
  TraceDetailResponse,
  SpanNode,
} from '@/utils/api-client/interfaces/telemetry';
import {
  TestResultDetail,
  ConversationTurn,
  GoalEvaluation,
} from '@/utils/api-client/interfaces/test-results';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [spanFiles, setSpanFiles] = useState<FileResponse[][]>([]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setSpanFiles([]);
    setTestResult(null);

    const load = async () => {
      const clientFactory = new ApiClientFactory(sessionToken);

      const testResultPromise = trace.test_result?.id
        ? clientFactory
            .getTestResultsClient()
            .getTestResult(trace.test_result.id)
        : Promise.resolve(null);

      const filesPromise = rootSpans
        ? Promise.all(
            rootSpans.map(async span => {
              if (!span.id) return [] as FileResponse[];
              try {
                return await clientFactory
                  .getFilesClient()
                  .getSpanFiles(span.id);
              } catch {
                return [] as FileResponse[];
              }
            })
          )
        : Promise.resolve([] as FileResponse[][]);

      try {
        const [result, files] = await Promise.all([
          testResultPromise,
          filesPromise,
        ]);
        setTestResult(result);
        setSpanFiles(files);
      } catch (err: unknown) {
        const errorMsg =
          err instanceof Error
            ? err.message
            : 'Failed to fetch test result details';
        setError(errorMsg);
        console.error('Failed to fetch trace data:', err);
      } finally {
        setLoading(false);
      }
    };

    load();
    // rootSpans is intentionally read from closure rather than listed as a
    // dependency.  The parent passes trace.root_spans which is a new array
    // reference on every render; trace.trace_id is the stable identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trace.trace_id, trace.test_result?.id, sessionToken]);

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

  const baseTurns =
    conversationSummary.length > 0 ? conversationSummary : spanConversation;

  const turns =
    spanFiles.length > 0
      ? baseTurns.map((turn, i) => ({
          ...turn,
          penelope_files: spanFiles[i] ?? [],
        }))
      : baseTurns;

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
      sessionToken={sessionToken}
    />
  );
}

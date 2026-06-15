'use client';

import { useState, useEffect, useMemo } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import {
  TraceDetailResponse,
  SpanNode,
  TRACE_REVIEW_TARGET_TYPES,
} from '@/utils/api-client/interfaces/telemetry';
import {
  TestResultDetail,
  ConversationTurn,
  GoalEvaluation,
  OverrideMarker,
  Review,
} from '@/utils/api-client/interfaces/test-results';
import { reconstructConversationFromSpans } from '@/utils/conversation-from-spans';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ConversationHistory from '@/components/common/ConversationHistory';

interface ConversationTraceViewProps {
  trace: TraceDetailResponse;
  sessionToken: string;
  onSpanSelect?: (span: SpanNode) => void;
  rootSpans?: SpanNode[];
  onReviewTurn?: (turnNumber: number, turnSuccess: boolean) => void;
}

interface TurnOverrideEntry {
  success: boolean;
  override: OverrideMarker;
}

/**
 * Read per-turn overrides from trace_metrics.turn_overrides.
 * Returns a map of turn number -> { success, override }.
 */
function getPerTurnOverrides(
  rootSpans: SpanNode[]
): Record<number, TurnOverrideEntry> {
  const traceMetrics = rootSpans.find(s => s.trace_metrics)?.trace_metrics as
    | Record<string, unknown>
    | undefined;
  if (!traceMetrics) return {};

  const turnOverrides = traceMetrics.turn_overrides as
    | Record<string, { success?: boolean; override?: OverrideMarker }>
    | undefined;
  if (!turnOverrides) return {};

  const result: Record<number, TurnOverrideEntry> = {};
  for (const [key, data] of Object.entries(turnOverrides)) {
    const turnNum = parseInt(key, 10);
    if (
      !isNaN(turnNum) &&
      data?.override &&
      typeof data.success === 'boolean'
    ) {
      result[turnNum] = {
        success: data.success,
        override: data.override,
      };
    }
  }
  return result;
}

export default function ConversationTraceView({
  trace,
  sessionToken,
  onSpanSelect,
  rootSpans,
  onReviewTurn,
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
    // rootSpans is intentionally omitted from deps. The parent derives it
    // directly from trace.root_spans, so it can only carry new spans when
    // trace.trace_id changes — which is already a dep. Adding rootSpans would
    // trigger a re-fetch on every render (new array reference each time).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trace.trace_id, trace.test_result?.id, sessionToken]);

  const turnReviewMap = useMemo(() => {
    const map = new Map<number, Review>();
    const reviews = rootSpans?.find(s => s.trace_reviews)?.trace_reviews
      ?.reviews;
    if (!reviews) return map;
    for (const review of reviews) {
      if (
        review.target?.type === TRACE_REVIEW_TARGET_TYPES.TURN &&
        review.target.reference
      ) {
        const turnNum = parseInt(
          review.target.reference.replace(/\D/g, ''),
          10
        );
        if (!isNaN(turnNum)) {
          const existing = map.get(turnNum);
          if (
            !existing ||
            (review.updated_at || '') > (existing.updated_at || '')
          ) {
            map.set(turnNum, review as unknown as Review);
          }
        }
      }
    }
    return map;
  }, [rootSpans]);

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

  const perTurnOverrides = rootSpans ? getPerTurnOverrides(rootSpans) : {};

  const overriddenTurns = baseTurns.map(turn => {
    const turnOverride = perTurnOverrides[turn.turn];
    if (turnOverride) {
      return {
        ...turn,
        success: turnOverride.success,
        override: turnOverride.override,
      };
    }
    return turn;
  });

  const turns =
    spanFiles.length > 0
      ? overriddenTurns.map((turn, i) => ({
          ...turn,
          penelope_files: spanFiles[i] ?? [],
        }))
      : overriddenTurns;

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
      onReviewTurn={onReviewTurn}
      maxHeight="100%"
      sessionToken={sessionToken}
      turnReviewMap={turnReviewMap}
    />
  );
}

'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import {
  TestResultDetail,
  Review,
  REVIEW_TARGET_TYPES,
} from '@/utils/api-client/interfaces/test-results';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import type {
  SpanNode,
  TraceSummary,
} from '@/utils/api-client/interfaces/telemetry';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ConversationHistory from '@/components/common/ConversationHistory';
import TraceDrawer from '@/app/(protected)/traces/components/TraceDrawer';
import {
  isMultiTurnTestResult,
  resolveConversationSummary,
} from '@/utils/conversation-from-spans';

interface TestDetailConversationTabProps {
  test: TestResultDetail;
  testSetType?: string;
  sessionToken: string;
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  onReviewTurn?: (turnNumber: number, turnSuccess: boolean) => void;
  onConfirmAutomatedReview?: () => void;
  isConfirmingReview?: boolean;
}

export default function TestDetailConversationTab({
  test,
  testSetType,
  sessionToken,
  project,
  projectName,
  onReviewTurn,
  onConfirmAutomatedReview,
  isConfirmingReview = false,
}: TestDetailConversationTabProps) {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [rootSpans, setRootSpans] = useState<SpanNode[]>([]);
  const [spanFiles, setSpanFiles] = useState<FileResponse[][]>([]);
  const [tracesLoading, setTracesLoading] = useState(false);
  const [traceDrawerOpen, setTraceDrawerOpen] = useState(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedTurnNumber, setSelectedTurnNumber] = useState<number | null>(
    null
  );

  const isMultiTurn = isMultiTurnTestResult(test, testSetType);

  // Fetch traces, trace detail, and span files in one chain.
  useEffect(() => {
    setSpanFiles([]);
    setTraces([]);
    setRootSpans([]);

    if (!test.id || !sessionToken || !isMultiTurn) return;

    const load = async () => {
      setTracesLoading(true);
      try {
        const factory = new ApiClientFactory(sessionToken);
        const telemetryClient = factory.getTelemetryClient();
        const response = await telemetryClient.listTraces({
          test_result_id: test.id as string,
          limit: 100,
        });
        const sorted = [...response.traces].sort(
          (a, b) =>
            new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
        );

        let files: FileResponse[][] = [];
        let spans: SpanNode[] = [];
        if (sorted.length > 0) {
          const detail = await telemetryClient.getTrace(
            sorted[0].trace_id,
            sorted[0].project_id
          );
          spans = detail.root_spans ?? [];

          const filesClient = factory.getFilesClient();
          files = await Promise.all(
            spans.map(async span => {
              if (!span.id) return [] as FileResponse[];
              try {
                return await filesClient.getSpanFiles(span.id);
              } catch {
                return [] as FileResponse[];
              }
            })
          );
        }

        setTraces(sorted);
        setRootSpans(spans);
        setSpanFiles(files);
      } catch {
        // Traces are optional; conversation may still come from test_output
      } finally {
        setTracesLoading(false);
      }
    };

    void load();
  }, [test.id, sessionToken, isMultiTurn]);

  const conversationSummary = useMemo(
    () => resolveConversationSummary(test, rootSpans, spanFiles),
    [test, rootSpans, spanFiles]
  );

  const hasConversation = isMultiTurn && conversationSummary.length > 0;

  const turnTraceMap = useMemo(() => {
    const map = new Map<number, TraceSummary>();
    if (traces.length > 0) {
      const trace = traces[0];
      conversationSummary
        .filter(t => t.target_response)
        .forEach(turn => {
          map.set(turn.turn, trace);
        });
    }
    return map;
  }, [traces, conversationSummary]);

  const projectId = traces[0]?.project_id || '';

  const handleResponseClick = useCallback(
    (turnNumber: number) => {
      const trace = turnTraceMap.get(turnNumber);
      if (trace) {
        setSelectedTraceId(trace.trace_id);
        setSelectedTurnNumber(turnNumber);
        setTraceDrawerOpen(true);
      }
    },
    [turnTraceMap]
  );

  const turnReviewMap = useMemo(() => {
    const map = new Map<number, Review>();
    const reviews = test.test_reviews?.reviews || [];
    for (const review of reviews) {
      if (
        review.target?.type === REVIEW_TARGET_TYPES.TURN &&
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
            map.set(turnNum, review);
          }
        }
      }
    }
    return map;
  }, [test.test_reviews]);

  if (!isMultiTurn) {
    const singleTurnSummary = [
      {
        turn: 1,
        timestamp: '',
        session_id: '',
        penelope_reasoning: '',
        penelope_message: test.test?.prompt?.content ?? '',
        target_response: test.test_output?.output ?? '',
        success: test.test_output?.goal_evaluation?.all_criteria_met ?? false,
      },
    ];

    return (
      <Box
        sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}
      >
        <ConversationHistory
          conversationSummary={singleTurnSummary}
          goalEvaluation={test.test_output?.goal_evaluation}
          project={project}
          projectName={projectName}
          onConfirmAutomatedReview={onConfirmAutomatedReview}
          hasExistingReview={!!test.last_review}
          reviewMatchesAutomated={test.matches_review === true}
          isConfirmingReview={isConfirmingReview}
          maxHeight="100%"
          sessionToken={sessionToken}
        />
      </Box>
    );
  }

  if (tracesLoading && !hasConversation) {
    return (
      <Box
        sx={{
          p: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 300,
        }}
      >
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (!hasConversation) {
    return (
      <Box
        sx={{
          p: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 300,
        }}
      >
        <Typography variant="body1" color="text.secondary">
          No conversation history available for this test.
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}
    >
      <ConversationHistory
        conversationSummary={conversationSummary}
        goalEvaluation={test.test_output?.goal_evaluation}
        project={project}
        projectName={projectName}
        onResponseClick={traces.length > 0 ? handleResponseClick : undefined}
        onReviewTurn={onReviewTurn}
        onConfirmAutomatedReview={onConfirmAutomatedReview}
        hasExistingReview={!!test.last_review}
        reviewMatchesAutomated={test.matches_review === true}
        isConfirmingReview={isConfirmingReview}
        maxHeight="100%"
        turnReviewMap={turnReviewMap}
        sessionToken={sessionToken}
      />
      <TraceDrawer
        open={traceDrawerOpen}
        onClose={() => {
          setTraceDrawerOpen(false);
          setSelectedTurnNumber(null);
        }}
        traceId={selectedTraceId}
        projectId={projectId}
        sessionToken={sessionToken}
        initialTurnIndex={
          selectedTurnNumber !== null ? selectedTurnNumber - 1 : undefined
        }
      />
    </Box>
  );
}

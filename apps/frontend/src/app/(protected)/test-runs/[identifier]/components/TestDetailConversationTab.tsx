'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import {
  TestResultDetail,
  ConversationTurn,
  Review,
  REVIEW_TARGET_TYPES,
} from '@/utils/api-client/interfaces/test-results';
import { TraceSummary } from '@/utils/api-client/interfaces/telemetry';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ConversationHistory from '@/components/common/ConversationHistory';
import TraceDrawer from '@/app/(protected)/traces/components/TraceDrawer';

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
  const [spanFiles, setSpanFiles] = useState<FileResponse[][]>([]);
  const [filesReady, setFilesReady] = useState(false);
  const [traceDrawerOpen, setTraceDrawerOpen] = useState(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedTurnNumber, setSelectedTurnNumber] = useState<number | null>(
    null
  );

  // Fetch traces, trace detail, and span files in one chain.
  // All state is set together at the end to avoid intermediate renders.
  useEffect(() => {
    if (!test.id || !sessionToken) return;

    const load = async () => {
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
        if (sorted.length > 0) {
          const detail = await telemetryClient.getTrace(
            sorted[0].trace_id,
            sorted[0].project_id
          );

          const filesClient = factory.getFilesClient();
          files = await Promise.all(
            detail.root_spans.map(async span => {
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
        if (files.some(f => f.length > 0)) {
          setSpanFiles(files);
        }
      } catch {
        // Silently fail — traces and files are optional
      } finally {
        setFilesReady(true);
      }
    };

    load();
  }, [test.id, sessionToken]);

  // Map turn numbers to trace — multi-turn conversations share a single trace
  // with each turn as a root span, so all turns map to the same trace
  const turnTraceMap = useMemo(() => {
    const map = new Map<number, TraceSummary>();
    if (traces.length > 0) {
      const trace = traces[0];
      const conversationTurns =
        test.test_output?.conversation_summary?.filter(
          t => t.target_response
        ) || [];
      conversationTurns.forEach(turn => {
        map.set(turn.turn, trace);
      });
    }
    return map;
  }, [traces, test.test_output?.conversation_summary]);

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

  // Build a map of turn number -> latest review targeting that turn
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

  // Determine if this is a multi-turn test
  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;

  // Get conversation summary, merging any span files as penelope_files
  const baseConversation = test.test_output?.conversation_summary;
  const conversationSummary: ConversationTurn[] | undefined = useMemo(() => {
    if (!baseConversation) return undefined;
    if (spanFiles.length === 0) return baseConversation;
    return baseConversation.map((turn, i) => ({
      ...turn,
      penelope_files: spanFiles[i] ?? [],
    }));
  }, [baseConversation, spanFiles]);
  const hasConversation =
    isMultiTurn && conversationSummary && conversationSummary.length > 0;

  // Wait for file loading to complete before rendering so files don't pop in
  if (isMultiTurn && hasConversation && !filesReady) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 300,
        }}
      >
        <CircularProgress size={32} />
      </Box>
    );
  }

  // If not a multi-turn test, show message
  if (!isMultiTurn) {
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
          Conversation history is only available for multi-turn tests.
        </Typography>
      </Box>
    );
  }

  // If no conversation available
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

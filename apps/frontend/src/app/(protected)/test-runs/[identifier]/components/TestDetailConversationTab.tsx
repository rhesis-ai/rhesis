'use client';

import { annotationsByTurn } from '@/components/annotations/annotation-summary';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Collapse,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { SectionField, FormattedText } from '@/components/common/TestText';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import {
  SpanNode,
  TraceSummary,
} from '@/utils/api-client/interfaces/telemetry';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import ConversationHistory from '@/components/common/ConversationHistory';
import TraceDrawer from '@/app/(protected)/traces/components/TraceDrawer';
import {
  conversationRootSpans,
  isMultiTurnTestResult,
  resolveConversationSummary,
  type TurnTraceTarget,
} from '@/utils/conversation-from-spans';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';
import { getEndpointFailure } from '@/utils/endpoint-failure';

interface TestDetailConversationTabProps {
  test: TestResultDetail;
  testSetType?: string;
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  onAnnotateTurn?: (turnNumber: number, turnPassed?: boolean) => void;
  onConfirmAutomatedAnnotation?: () => void;
  isConfirmingAnnotation?: boolean;
  onShowEvaluation?: () => void;
  metricsSource?: string;
  onOverrideVerdict?: () => void;
  onUndoReview?: () => void;
  isUndoingReview?: boolean;
}

/** The scenario and instructions Penelope followed, closed until asked for. */
function SimulationSetup({ test }: { test: TestResultDetail }) {
  const [open, setOpen] = useState(false);
  const config = test.test_output?.test_configuration;
  if (!config?.scenario && !config?.instructions) return null;
  return (
    <Box
      sx={{
        mx: 3,
        px: 2,
        py: 1,
        borderRadius: BORDER_RADIUS.md,
        border: 1,
        borderColor: 'divider',
      }}
    >
      <Button
        size="small"
        color="inherit"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        endIcon={
          <ExpandMoreIcon
            sx={{ transform: open ? 'rotate(180deg)' : 'none' }}
          />
        }
        sx={{ textTransform: 'none', fontWeight: 600, px: 0 }}
      >
        <Typography variant="body2" component="span" fontWeight={600}>
          Simulation setup
        </Typography>
      </Button>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, py: 1.5 }}>
          {config.scenario && (
            <SectionField label="Scenario">
              <FormattedText text={config.scenario} />
            </SectionField>
          )}
          {config.instructions && (
            <SectionField label="Instructions">
              <FormattedText text={config.instructions} />
            </SectionField>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}

export default function TestDetailConversationTab({
  test,
  testSetType,
  project,
  projectName,
  onAnnotateTurn,
  onConfirmAutomatedAnnotation,
  isConfirmingAnnotation = false,
  onShowEvaluation,
  metricsSource,
  onOverrideVerdict,
  onUndoReview,
  isUndoingReview,
}: TestDetailConversationTabProps) {
  const { status } = useSession();
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [rootSpans, setRootSpans] = useState<SpanNode[]>([]);
  const [turnTargets, setTurnTargets] = useState<TurnTraceTarget[]>([]);
  const [spanFiles, setSpanFiles] = useState<FileResponse[][]>([]);
  const [tracesLoading, setTracesLoading] = useState(false);
  const [traceDrawerOpen, setTraceDrawerOpen] = useState(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedRootIndex, setSelectedRootIndex] = useState<number | null>(
    null
  );

  const isMultiTurn = isMultiTurnTestResult(test, testSetType);

  // Fetch traces, trace detail, and span files in one chain.
  useEffect(() => {
    setSpanFiles([]);
    setTraces([]);
    setRootSpans([]);
    setTurnTargets([]);

    if (!test.id || !isAuthenticated(status) || !isMultiTurn) return;

    const load = async () => {
      setTracesLoading(true);
      try {
        const factory = new ApiClientFactory();
        const telemetryClient = factory.getTelemetryClient();
        const response = await telemetryClient.listTraces({
          test_result_id: test.id as string,
          limit: 100,
        });
        const sorted = [...response.traces].sort(
          (a, b) =>
            new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
        );

        const details = await Promise.all(
          sorted.map(trace =>
            telemetryClient.getTrace(trace.trace_id, trace.project_id)
          )
        );
        const { spans, targets } = conversationRootSpans(
          sorted.map((trace, i) => ({
            traceId: trace.trace_id,
            rootSpans: details[i].root_spans ?? [],
          }))
        );

        const filesClient = factory.getFilesClient();
        const files = await Promise.all(
          spans.map(async span => {
            if (!span.id) return [] as FileResponse[];
            try {
              return await filesClient.getSpanFiles(span.id);
            } catch {
              return [] as FileResponse[];
            }
          })
        );

        setTraces(sorted);
        setRootSpans(spans);
        setTurnTargets(targets);
        setSpanFiles(files);
      } catch {
        // Traces are optional; conversation may still come from test_output
      } finally {
        setTracesLoading(false);
      }
    };

    void load();
  }, [test.id, isMultiTurn, status]);

  const conversationSummary = useMemo(
    () => resolveConversationSummary(test, rootSpans, spanFiles),
    [test, rootSpans, spanFiles]
  );

  const hasConversation = isMultiTurn && conversationSummary.length > 0;

  const turnTraceMap = useMemo(() => {
    const map = new Map<number, TurnTraceTarget>();
    conversationSummary
      .filter(t => t.target_response)
      .forEach(turn => {
        const target = turnTargets[turn.turn - 1];
        if (target) map.set(turn.turn, target);
      });
    return map;
  }, [turnTargets, conversationSummary]);

  const projectId = traces[0]?.project_id || '';

  const handleResponseClick = useCallback(
    (turnNumber: number) => {
      const target = turnTraceMap.get(turnNumber);
      if (target) {
        setSelectedTraceId(target.traceId);
        setSelectedRootIndex(target.rootIndex);
        setTraceDrawerOpen(true);
      }
    },
    [turnTraceMap]
  );

  const turnAnnotationMap = useMemo(
    () => annotationsByTurn(test.annotation_summary),
    [test.annotation_summary]
  );

  if (!isMultiTurn) {
    // With no `output` (a rejected call), the turn used to render as an empty bubble and
    // was then dropped by ConversationHistory's "nothing to show" filter, so the tab read
    // "No conversation history available". Show what the endpoint actually sent back.
    const endpointFailure = getEndpointFailure(test.test_output);
    const singleTurnSummary = [
      {
        turn: 1,
        timestamp: '',
        session_id: '',
        penelope_reasoning: '',
        penelope_message: test.test?.prompt?.content ?? '',
        // `||`, not `??`: an empty-string output hits the same dropped-turn path as a
        // missing one, and is what a rejected call actually leaves behind.
        target_response:
          test.test_output?.output ||
          endpointFailure?.responseBody ||
          endpointFailure?.summary ||
          '',
        // Single-turn results have no goal_evaluation, so the turn status comes
        // from the result status (review > backend status > metrics).
        success: getEffectiveTestResultStatus(test) === 'Pass',
      },
    ];

    return (
      <Box
        sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}
      >
        <ConversationHistory
          conversationSummary={singleTurnSummary}
          goalEvaluation={test.test_output?.goal_evaluation}
          metrics={test.test_metrics?.metrics}
          project={project}
          projectName={projectName}
          onConfirmAutomatedAnnotation={onConfirmAutomatedAnnotation}
          hasExistingAnnotation={!!test.last_annotation}
          annotationMatchesAutomated={test.matches_annotation === true}
          isConfirmingAnnotation={isConfirmingAnnotation}
          maxHeight="100%"
          resultStatus={getEffectiveTestResultStatus(test)}
          onShowEvaluation={onShowEvaluation}
          requirementName={test.test?.requirement?.name}
          metricsSource={metricsSource}
          reviewerName={test.last_annotation?.user?.name}
          onOverrideVerdict={onOverrideVerdict}
          onUndoReview={onUndoReview}
          isUndoingReview={isUndoingReview}
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
      <SimulationSetup test={test} />
      <ConversationHistory
        conversationSummary={conversationSummary}
        goalEvaluation={test.test_output?.goal_evaluation}
        metrics={test.test_metrics?.metrics}
        project={project}
        projectName={projectName}
        onResponseClick={traces.length > 0 ? handleResponseClick : undefined}
        onAnnotateTurn={onAnnotateTurn}
        onConfirmAutomatedAnnotation={onConfirmAutomatedAnnotation}
        hasExistingAnnotation={!!test.last_annotation}
        annotationMatchesAutomated={test.matches_annotation === true}
        isConfirmingAnnotation={isConfirmingAnnotation}
        maxHeight="100%"
        turnAnnotationMap={turnAnnotationMap}
        resultStatus={getEffectiveTestResultStatus(test)}
        onShowEvaluation={onShowEvaluation}
        requirementName={test.test?.requirement?.name}
        metricsSource={metricsSource}
        reviewerName={test.last_annotation?.user?.name}
        onOverrideVerdict={onOverrideVerdict}
        onUndoReview={onUndoReview}
        isUndoingReview={isUndoingReview}
      />
      <TraceDrawer
        open={traceDrawerOpen}
        onClose={() => {
          setTraceDrawerOpen(false);
          setSelectedRootIndex(null);
        }}
        traceId={selectedTraceId}
        projectId={projectId}
        initialTurnIndex={selectedRootIndex ?? undefined}
      />
    </Box>
  );
}

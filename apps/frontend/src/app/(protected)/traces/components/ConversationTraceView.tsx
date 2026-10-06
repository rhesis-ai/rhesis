'use client';

import { annotationsByTurn } from '@/components/annotations/annotation-summary';
import { useState, useEffect, useMemo } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import {
  TraceDetailResponse,
  SpanNode,
} from '@/utils/api-client/interfaces/telemetry';
import {
  TestResultDetail,
  ConversationTurn,
  GoalEvaluation,
  OverrideMarker,
} from '@/utils/api-client/interfaces/test-results';
import {
  conversationToMessages,
  reconstructConversationFromSpans,
  traceMetricsFromSpans,
  turnToMessages,
} from '@/utils/conversation-from-spans';
import type { ConversationMessage } from '@/utils/api-client/interfaces/tests';
import { TEST_TYPES, type TestTypeValue } from '@/constants/test-types';
import CreateTestFromConversationDrawer from '@/components/tests/CreateTestFromConversationDrawer';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ConversationHistory from '@/components/common/ConversationHistory';
import {
  DeletedEntityAlert,
  type DeletedEntityData,
} from '@/components/common/DeletedEntityAlert';
import {
  getDeletedEntityData,
  isDeletedEntityError,
} from '@/utils/entity-error-handler';

interface ConversationTraceViewProps {
  trace: TraceDetailResponse;
  onSpanSelect?: (span: SpanNode) => void;
  rootSpans?: SpanNode[];
  onAnnotateTurn?: (turnNumber: number, turnPassed?: boolean) => void;
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

function deletedTestResultFallback(testResultId: string): DeletedEntityData {
  return {
    model_name: 'TestResult',
    model_name_display: 'Test Result',
    item_id: testResultId,
    table_name: 'test_result',
    restore_url: `/recycle/test_result/${testResultId}/restore`,
    message: 'The test for this trace no longer exists.',
  };
}

export default function ConversationTraceView({
  trace,
  onSpanSelect,
  rootSpans,
  onAnnotateTurn,
}: ConversationTraceViewProps) {
  const notifications = useNotifications();
  const canCreateTest = useCan(Capability.Test.CREATE);
  const [testDraft, setTestDraft] = useState<{
    type: TestTypeValue;
    messages: ConversationMessage[];
  } | null>(null);
  const [testResult, setTestResult] = useState<TestResultDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletedTestResult, setDeletedTestResult] =
    useState<DeletedEntityData | null>(null);
  const [spanFiles, setSpanFiles] = useState<FileResponse[][]>([]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setDeletedTestResult(null);
    setSpanFiles([]);
    setTestResult(null);

    const load = async () => {
      const clientFactory = new ApiClientFactory();
      let result: TestResultDetail | null = null;
      let deleted: DeletedEntityData | null = null;
      let fetchError: string | null = null;

      if (trace.test_result?.id) {
        try {
          result = await clientFactory
            .getTestResultsClient()
            .getTestResult(trace.test_result.id);
        } catch (err: unknown) {
          if (isDeletedEntityError(err)) {
            deleted =
              getDeletedEntityData(err) ??
              deletedTestResultFallback(trace.test_result.id);
          } else {
            fetchError =
              err instanceof Error
                ? err.message
                : 'Failed to fetch test result details';
            console.error('Failed to fetch test result:', err);
          }
        }
      }

      let files: FileResponse[][] = [];
      if (rootSpans) {
        files = await Promise.all(
          rootSpans.map(async span => {
            if (!span.id) return [] as FileResponse[];
            try {
              return await clientFactory.getFilesClient().getSpanFiles(span.id);
            } catch {
              return [] as FileResponse[];
            }
          })
        );
      }

      setTestResult(result);
      setDeletedTestResult(deleted);
      setError(fetchError);
      setSpanFiles(files);
      setLoading(false);
    };

    void load();
    // rootSpans is intentionally omitted from deps. The parent derives it
    // directly from trace.root_spans, so it can only carry new spans when
    // trace.trace_id changes — which is already a dep. Adding rootSpans would
    // trigger a re-fetch on every render (new array reference each time).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trace.trace_id, trace.test_result?.id]);

  const turnAnnotationMap = useMemo(
    () =>
      annotationsByTurn(
        rootSpans?.find(s => s.annotation_summary)?.annotation_summary
      ),
    [rootSpans]
  );

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

  const deletedTestWarning = deletedTestResult ? (
    <Box sx={{ p: 2, flexShrink: 0 }}>
      <DeletedEntityAlert entityData={deletedTestResult} />
    </Box>
  ) : null;

  const fetchErrorWarning = error ? (
    <Box sx={{ p: 2, flexShrink: 0 }}>
      <Alert severity="error">{error}</Alert>
    </Box>
  ) : null;

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
      <Box sx={{ p: 3 }}>
        {deletedTestWarning}
        {fetchErrorWarning}
        {!deletedTestWarning && !fetchErrorWarning && (
          <Alert severity="info">
            No conversation data is available from this trace.
          </Alert>
        )}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
      }}
    >
      {deletedTestWarning}
      {fetchErrorWarning}
      {canCreateTest && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            px: 2,
            pt: 1,
          }}
        >
          <Tooltip title="Create multi-turn test from conversation">
            <IconButton
              size="small"
              aria-label="Create multi-turn test from conversation"
              onClick={() =>
                setTestDraft({
                  type: TEST_TYPES.MULTI_TURN,
                  messages: conversationToMessages(turns),
                })
              }
            >
              <ScienceOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      )}
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <ConversationHistory
          conversationSummary={turns}
          goalEvaluation={
            conversationSummary.length > 0 ? goalEvaluation : undefined
          }
          metrics={
            conversationSummary.length > 0
              ? testResult?.test_metrics?.metrics
              : rootSpans && traceMetricsFromSpans(rootSpans)
          }
          project={trace.project}
          onResponseClick={
            onSpanSelect && rootSpans ? handleResponseClick : undefined
          }
          onAnnotateTurn={onAnnotateTurn}
          onCreateTestFromTurn={
            canCreateTest
              ? turnNumber => {
                  const turn = turns.find(t => t.turn === turnNumber);
                  if (!turn) return;
                  setTestDraft({
                    type: TEST_TYPES.SINGLE_TURN,
                    messages: turnToMessages(turn),
                  });
                }
              : undefined
          }
          maxHeight="100%"
          turnAnnotationMap={turnAnnotationMap}
        />
      </Box>
      {testDraft && (
        <CreateTestFromConversationDrawer
          open
          onClose={() => setTestDraft(null)}
          messages={testDraft.messages}
          testType={testDraft.type}
          endpointId={trace.endpoint?.id}
          onSuccess={() =>
            notifications.show('Test created successfully', {
              severity: 'success',
              autoHideDuration: 4000,
            })
          }
        />
      )}
    </Box>
  );
}

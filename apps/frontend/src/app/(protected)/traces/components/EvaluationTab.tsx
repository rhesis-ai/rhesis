'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import {
  Alert,
  Box,
  CircularProgress,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import { format } from 'date-fns';
import { RateReviewIcon } from '@/components/icons';
import AnnotationIndicator from '@/components/annotations/AnnotationIndicator';
import { annotationsByMetric } from '@/components/annotations/annotation-summary';
import { DeletedEntityAlert } from '@/components/common/DeletedEntityAlert';
import type { MentionOption } from '@/components/common/MentionTextInput';
import {
  ANNOTATION_TARGET_TYPES,
  type AnnotationSummaryEntry,
} from '@/utils/api-client/interfaces/annotation';
import {
  TRACE_METRICS_STATUS,
  type SpanNode,
  type TraceDetailResponse,
  type TraceMetricsStatus,
} from '@/utils/api-client/interfaces/telemetry';
import type {
  MetricResult,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';
import type { TestResultStatus } from '@/constants/outcomes';
import {
  buildResultChecks,
  checksSummary,
  type ResultCheck,
  type ResultCheckGroup,
} from '@/utils/result-checks';
import {
  getEffectiveTestResultStatus,
  isPassedStatusName,
} from '@/utils/test-result-status';
import CheckSection, { SectionText } from '@/components/common/CheckSection';
import EvaluationVerdict from './EvaluationVerdict';
import TraceAnnotationsTab from './TraceAnnotationsTab';
import { automatedVerdictFor } from './trace-verdict';
import { useTraceTestResult } from './useTraceTestResult';

interface EvaluationTabProps {
  span: SpanNode;
  trace: TraceDetailResponse;
  isConversationTrace: boolean;
  selectedTurnNumber: number | null;
  traceMetricsStatus: TraceMetricsStatus | null;
  onAnnotateMetric?: (metricName: string) => void;
  onAnnotateTrace?: () => void;
  onAnnotateTurn?: (turnNumber: number, turnPassed?: boolean) => void;
  onTraceUpdated: () => void;
  mentionableMetrics: MentionOption[];
  mentionableTurns: MentionOption[];
}

interface MetricSection {
  metrics?: Record<string, MetricResult>;
}

/** A span's own metrics as check rows, so they read like the test's. */
function metricChecks(metrics: Record<string, MetricResult>): ResultCheck[] {
  return Object.entries(metrics).map(([name, result]) => ({
    key: name,
    label: name,
    passed:
      !result.error && typeof result.is_successful === 'boolean'
        ? result.is_successful
        : null,
    reason: result.reason ?? '',
    relevantTurns: [],
    metric: name,
    result,
  }));
}

function metricAnnotationsOf(
  summary: Record<string, AnnotationSummaryEntry> | undefined
): Map<string, AnnotationSummaryEntry> {
  const map = new Map<string, AnnotationSummaryEntry>();
  for (const entry of Object.values(summary ?? {})) {
    if (
      entry.target_type === ANNOTATION_TARGET_TYPES.METRIC &&
      entry.reference
    ) {
      map.set(entry.reference, entry);
    }
  }
  return map;
}

function Marker({
  annotation,
  overruled,
}: {
  annotation?: AnnotationSummaryEntry;
  overruled: boolean;
}) {
  if (!annotation) return null;
  return (
    <AnnotationIndicator
      verdict={
        annotation.status?.name
          ? isPassedStatusName(annotation.status.name)
            ? 'passed'
            : 'failed'
          : null
      }
      hasConflict={overruled}
      annotator={annotation.user?.name}
      comment={annotation.comments}
    />
  );
}

function AnnotateButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <Tooltip title={label}>
      <IconButton
        size="small"
        aria-label={label}
        onClick={onClick}
        sx={{ p: 0.25, color: 'text.secondary' }}
      >
        <RateReviewIcon sx={{ fontSize: theme => theme.spacing(2) }} />
      </IconButton>
    </Tooltip>
  );
}

/** What the test's checks were read from: its goal and restrictions, or the requirement. */
function groupIntro(group: ResultCheckGroup, test: TestResultDetail) {
  if (group.key === 'test') {
    const config = test.test_output?.test_configuration;
    const prompt = test.test?.prompt?.content;
    if (!config?.goal && !config?.restrictions && !prompt) return null;
    return (
      <>
        {config?.goal && <SectionText label="Goal">{config.goal}</SectionText>}
        {config?.restrictions && (
          <SectionText label="Restrictions">{config.restrictions}</SectionText>
        )}
        {!config?.goal && prompt && (
          <SectionText label="Prompt">{prompt}</SectionText>
        )}
      </>
    );
  }
  return null;
}

/** "Multi-turn · 6 of 6 turns · Oct 20, 2:15 PM" */
function testMeta(test: TestResultDetail, isConversation: boolean): string {
  const parts = [isConversation ? 'Multi-turn' : 'Single-turn'];
  const used = test.test_output?.turns_used;
  const max = test.test_output?.test_configuration?.max_turns;
  if (used) parts.push(max ? `${used} of ${max} turns` : `${used} turns`);
  if (test.created_at) parts.push(format(new Date(test.created_at), 'PPp'));
  return parts.join(' · ');
}

/**
 * Laid out like the test run's Evaluation tab, but flat: the result and its
 * tally, the test's checks, the span's own metrics, then the annotations.
 */
export default function EvaluationTab({
  span,
  trace,
  isConversationTrace,
  selectedTurnNumber,
  traceMetricsStatus,
  onAnnotateMetric,
  onAnnotateTrace,
  onAnnotateTurn,
  onTraceUpdated,
  mentionableMetrics,
  mentionableTurns,
}: EvaluationTabProps) {
  const { testResult, loading, error, deleted } = useTraceTestResult(trace);

  const testGroups = useMemo(
    () =>
      testResult
        ? buildResultChecks({
            metrics: testResult.test_metrics?.metrics,
            goalEvaluation: testResult.test_output?.goal_evaluation,
            requirementName: testResult.test?.requirement?.name,
          })
        : [],
    [testResult]
  );

  // Same filter as the conversation view, so turn tags match the turns shown there.
  const turnCount = useMemo(() => {
    const turns = (testResult?.test_output?.conversation_summary ?? []).filter(
      turn => turn.penelope_message || turn.target_response
    );
    return turns.length || undefined;
  }, [testResult]);

  const traceMetrics = span.trace_metrics as
    | Record<string, MetricSection | undefined>
    | undefined;
  const turnChecks = metricChecks(traceMetrics?.turn_metrics?.metrics ?? {});
  const conversationChecks = isConversationTrace
    ? metricChecks(traceMetrics?.conversation_metrics?.metrics ?? {})
    : [];

  const testAnnotations = useMemo(
    () => metricAnnotationsOf(testResult?.annotation_summary),
    [testResult?.annotation_summary]
  );
  const spanAnnotations = useMemo(
    () => annotationsByMetric(span.annotation_summary),
    [span.annotation_summary]
  );

  const spanVerdict = automatedVerdictFor(span);
  const status: TestResultStatus | null = testResult
    ? getEffectiveTestResultStatus(testResult)
    : spanVerdict
      ? spanVerdict.passed
        ? 'Pass'
        : 'Fail'
      : null;
  const allChecks: ResultCheckGroup[] = [
    ...testGroups,
    {
      key: 'metrics',
      title: '',
      checks: [...turnChecks, ...conversationChecks],
    },
  ];
  const hasChecks = allChecks.some(g => g.checks.length > 0);

  const turnPassed =
    turnChecks.length > 0 ? turnChecks.every(c => c.passed) : undefined;

  const spanMetricActions = (check: ResultCheck) => (
    <>
      <Marker
        annotation={spanAnnotations.get(check.metric)}
        overruled={!!check.result?.override}
      />
      {onAnnotateMetric && (
        <AnnotateButton
          label={`Annotate ${check.metric}`}
          onClick={() => onAnnotateMetric(check.metric)}
        />
      )}
    </>
  );

  return (
    <Box
      sx={{
        px: 2,
        py: 1.5,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      <Box>
        <EvaluationVerdict
          span={span}
          status={status}
          summary={hasChecks ? checksSummary(allChecks) : null}
          onAnnotate={onAnnotateTrace}
          onChanged={onTraceUpdated}
        />
        {testResult && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.75 }}>
            <Typography variant="caption" color="text.secondary">
              {testMeta(testResult, isConversationTrace)}
            </Typography>
            {trace.test && (
              <Typography
                variant="caption"
                component={Link}
                href={`/tests/${trace.test.id}`}
                target="_blank"
                sx={{
                  color: 'primary.main',
                  textDecoration: 'none',
                  '&:hover': { textDecoration: 'underline' },
                }}
              >
                Open test
              </Typography>
            )}
          </Box>
        )}
      </Box>

      {traceMetricsStatus === TRACE_METRICS_STATUS.ERROR && (
        <Alert severity="error" sx={{ py: 0 }}>
          Metric evaluation errored for this trace; results may be incomplete.
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ py: 0 }}>
          {error}
        </Alert>
      )}
      {deleted && <DeletedEntityAlert entityData={deleted} />}
      {loading && <CircularProgress size={20} />}

      {testResult &&
        testGroups.map(group => (
          <CheckSection
            key={group.key + group.title}
            title={group.title}
            titleHint={
              group.title.startsWith('Requirement:')
                ? testResult.test?.requirement?.description
                : undefined
            }
            checks={group.checks}
            turnCount={turnCount}
            intro={groupIntro(group, testResult)}
            headerActions={
              group.metric && (
                <Marker
                  annotation={testAnnotations.get(group.metric)}
                  overruled={
                    !!testResult.test_metrics?.metrics?.[group.metric]?.override
                  }
                />
              )
            }
            rowActions={
              group.metric
                ? undefined
                : check => (
                    <Marker
                      annotation={testAnnotations.get(check.metric)}
                      overruled={!!check.result?.override}
                    />
                  )
            }
          />
        ))}

      {turnChecks.length > 0 && (
        <CheckSection
          title={
            isConversationTrace && selectedTurnNumber != null
              ? `Turn ${selectedTurnNumber} metrics`
              : 'Span metrics'
          }
          checks={turnChecks}
          headerActions={
            isConversationTrace &&
            selectedTurnNumber != null &&
            onAnnotateTurn && (
              <AnnotateButton
                label={`Annotate turn ${selectedTurnNumber}`}
                onClick={() => onAnnotateTurn(selectedTurnNumber, turnPassed)}
              />
            )
          }
          rowActions={spanMetricActions}
        />
      )}

      {conversationChecks.length > 0 && (
        <CheckSection
          title="Conversation metrics"
          checks={conversationChecks}
          rowActions={spanMetricActions}
        />
      )}

      {!loading && !hasChecks && (
        <Typography variant="body2" color="text.secondary">
          No checks were recorded for this span.
        </Typography>
      )}

      <Box
        component="section"
        sx={{ borderTop: 1, borderColor: 'divider', pt: 1 }}
      >
        <TraceAnnotationsTab
          selectedSpan={span}
          trace={trace}
          onTraceUpdated={onTraceUpdated}
          mentionableMetrics={mentionableMetrics}
          mentionableTurns={mentionableTurns}
          compact
        />
      </Box>
    </Box>
  );
}

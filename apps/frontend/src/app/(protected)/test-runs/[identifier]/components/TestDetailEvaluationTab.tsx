'use client';

import React, { useMemo, useState } from 'react';
import {
  ANNOTATION_TARGET_TYPES,
  type AnnotationSummaryEntry,
} from '@/utils/api-client/interfaces/annotation';
import {
  Box,
  Typography,
  Paper,
  Collapse,
  IconButton,
  Tooltip,
  Alert,
  AlertTitle,
  useTheme,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RateReviewIcon from '@mui/icons-material/RateReview';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { MetricsSource } from '@/utils/api-client/interfaces/test-configuration';
import StatusChip from '@/components/common/StatusChip';
import AnnotationIndicator from '@/components/annotations/AnnotationIndicator';
import { STATUS_LABEL } from '@/constants/outcomes';
import { getEndpointFailure } from '@/utils/endpoint-failure';
import {
  getEffectiveTestResultStatus,
  hasConflictingAnnotation,
  isPassedStatusName,
} from '@/utils/test-result-status';
import ResultCheckCard from '@/components/common/ResultCheckCard';
import {
  SectionField,
  TextContent,
  asSentenceList,
  renderFormattedText,
} from '@/components/common/TestText';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import { testPreviewSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import {
  buildResultChecks,
  checksSummary,
  type ResultCheckGroup,
} from '@/utils/result-checks';

interface TestDetailEvaluationTabProps {
  test: TestResultDetail;
  /** Source of metrics used in this test run */
  metricsSource?: MetricsSource | string;
  onAnnotateMetric?: (metricName: string) => void;
  /** Only a single-turn result's prompt carries an expected response. */
  expectedResponse?: string;
}

const annotationVerdict = (entry?: AnnotationSummaryEntry) =>
  entry?.status?.name
    ? isPassedStatusName(entry.status.name)
      ? ('passed' as const)
      : ('failed' as const)
    : null;

function AnnotateButton({ onClick }: { onClick: () => void }) {
  const theme = useTheme();
  return (
    <Tooltip title="Annotate">
      <IconButton
        size="small"
        aria-label="Annotate"
        onClick={onClick}
        sx={{
          p: 0.5,
          color: 'text.secondary',
          '&:hover': { color: 'primary.main' },
        }}
      >
        <RateReviewIcon sx={{ fontSize: theme.spacing(2) }} />
      </IconButton>
    </Tooltip>
  );
}

/** The annotation mark plus the annotate button for one metric. */
function MetricActions({
  metric,
  annotation,
  overruled,
  onAnnotateMetric,
}: {
  metric: string;
  annotation?: AnnotationSummaryEntry;
  overruled: boolean;
  onAnnotateMetric?: (metricName: string) => void;
}) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
      {annotation && (
        <AnnotationIndicator
          verdict={annotationVerdict(annotation)}
          hasConflict={overruled}
          annotator={annotation.user?.name}
          comment={annotation.comments}
        />
      )}
      {onAnnotateMetric && (
        <AnnotateButton onClick={() => onAnnotateMetric(metric)} />
      )}
    </Box>
  );
}

/** The judge's overall reasoning, which mostly restates the criteria, so it starts closed. */
function Reasoning({
  reason,
  evidence,
}: {
  reason: string;
  evidence: string[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <Box sx={{ px: 2.25, py: 1, borderTop: 1, borderColor: 'divider' }}>
      <Box
        component="button"
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          p: 0,
          border: 'none',
          bgcolor: 'transparent',
          cursor: 'pointer',
          color: 'text.secondary',
          font: 'inherit',
        }}
      >
        <Typography variant="body2" fontWeight={500}>
          Reasoning
        </Typography>
        <ExpandMoreIcon
          fontSize="small"
          sx={{ transform: open ? 'rotate(180deg)' : 'none' }}
        />
      </Box>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {reason}
        </Typography>
        {evidence.map((item, index) => (
          <Typography
            // eslint-disable-next-line react/no-array-index-key -- display-only, never reorders
            key={index}
            variant="body2"
            color="text.secondary"
            sx={{ mt: 0.5 }}
          >
            {`• ${item}`}
          </Typography>
        ))}
      </Collapse>
    </Box>
  );
}

interface CheckGroupCardProps {
  group: ResultCheckGroup;
  test: TestResultDetail;
  turnCount?: number;
  annotations: Map<string, AnnotationSummaryEntry>;
  onAnnotateMetric?: (metricName: string) => void;
}

/** What a group's checks were read from: the test's goal and restrictions, or the requirement. */
function groupIntro(
  group: ResultCheckGroup,
  test: TestResultDetail
): React.ReactNode {
  if (group.key === 'test') {
    const config = test.test_output?.test_configuration;
    if (!config?.goal && !config?.restrictions) return null;
    return (
      <>
        {config.goal && (
          <SectionField label="Goal">
            <TextContent text={config.goal} />
          </SectionField>
        )}
        {config.restrictions && (
          <SectionField label="Restrictions">
            {renderFormattedText(asSentenceList(config.restrictions))}
          </SectionField>
        )}
      </>
    );
  }
  const requirement = test.test?.requirement;
  if (!requirement?.description || !group.title.startsWith('Requirement:')) {
    return null;
  }
  return (
    <Typography variant="body2" color="text.secondary">
      {requirement.description}
    </Typography>
  );
}

/** A single-turn response is judged against these; the prompt and response are the conversation. */
function JudgedAgainst({
  test,
  expectedResponse,
}: {
  test: TestResultDetail;
  expectedResponse?: string;
}) {
  const contextItems =
    test.test_output?.context?.filter(item => item.trim()) ?? [];
  const metadata = test.test_output?.metadata;
  const hasMetadata = !!metadata && Object.keys(metadata).length > 0;
  if (!expectedResponse && contextItems.length === 0 && !hasMetadata) {
    return null;
  }
  return (
    <Paper
      variant="outlined"
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        px: 2.25,
        py: 1.75,
        borderRadius: BORDER_RADIUS.md,
        borderColor: 'divider',
        boxShadow: ELEVATION.xs,
      }}
    >
      <Typography variant="subtitle1" component="h3" fontWeight={600}>
        Judged against
      </Typography>
      {expectedResponse && (
        <SectionField label="Expected response">
          <TextContent text={expectedResponse} />
        </SectionField>
      )}
      {contextItems.length > 0 && (
        <SectionField label={`Context (${contextItems.length})`}>
          {renderFormattedText(contextItems.map(c => `- ${c}`).join('\n'))}
        </SectionField>
      )}
      {hasMetadata && (
        <SectionField label="Metadata">
          <Box
            component="pre"
            sx={{ ...testPreviewSx, minHeight: 'unset', m: 0 }}
          >
            <JsonPreview value={metadata} />
          </Box>
        </SectionField>
      )}
    </Paper>
  );
}

function CheckGroupCard({
  group,
  test,
  turnCount,
  annotations,
  onAnnotateMetric,
}: CheckGroupCardProps) {
  const groupMetric = group.metric
    ? test.test_metrics?.metrics?.[group.metric]
    : undefined;
  const showReasoning =
    !!groupMetric?.reason && group.checks.every(c => !c.result);

  return (
    <ResultCheckCard
      group={group}
      turnCount={turnCount}
      intro={groupIntro(group, test)}
      headerActions={
        group.metric && (
          <MetricActions
            metric={group.metric}
            annotation={annotations.get(group.metric)}
            overruled={!!groupMetric?.override}
            onAnnotateMetric={onAnnotateMetric}
          />
        )
      }
      rowActions={
        group.metric
          ? undefined
          : check => (
              <MetricActions
                metric={check.metric}
                annotation={annotations.get(check.metric)}
                overruled={!!check.result?.override}
                onAnnotateMetric={onAnnotateMetric}
              />
            )
      }
      footer={
        showReasoning &&
        groupMetric && (
          <Reasoning
            reason={groupMetric.reason}
            evidence={test.test_output?.goal_evaluation?.evidence ?? []}
          />
        )
      }
    />
  );
}

export default function TestDetailEvaluationTab({
  test,
  metricsSource,
  onAnnotateMetric,
  expectedResponse,
}: TestDetailEvaluationTabProps) {
  const groups = useMemo(
    () =>
      buildResultChecks({
        metrics: test.test_metrics?.metrics,
        goalEvaluation: test.test_output?.goal_evaluation,
        requirementName: test.test?.requirement?.name,
        metricsSource,
      }),
    [test, metricsSource]
  );

  // Same filter as the conversation view, so "All turns" means the turns shown there.
  const turnCount = useMemo(() => {
    const turns = (test.test_output?.conversation_summary ?? []).filter(
      turn => turn.penelope_message || turn.target_response
    );
    return turns.length || undefined;
  }, [test.test_output?.conversation_summary]);

  // metric name -> the annotation on that metric. The summary is already
  // reduced to the newest per target, so there is no comparison to make.
  const metricAnnotations = useMemo(() => {
    const map = new Map<string, AnnotationSummaryEntry>();
    for (const entry of Object.values(test.annotation_summary ?? {})) {
      if (
        entry.target_type === ANNOTATION_TARGET_TYPES.METRIC &&
        entry.reference
      ) {
        map.set(entry.reference, entry);
      }
    }
    return map;
  }, [test.annotation_summary]);

  const status = getEffectiveTestResultStatus(test);
  const endpointFailure = getEndpointFailure(test.test_output);

  // Nothing was evaluated because the endpoint never answered. A "0 of 0 checks passed"
  // line would read as a real score rather than as an absence of one.
  if (endpointFailure && status === 'Error' && groups.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning" icon={<ErrorOutlineIcon />}>
          <AlertTitle>
            {endpointFailure.statusCode !== undefined
              ? `Not scored: target endpoint returned HTTP ${endpointFailure.statusCode}`
              : 'Not scored: target endpoint did not return a response'}
          </AlertTitle>
          <Typography variant="body2">
            No metrics were evaluated, because there was no response to evaluate
            them against. See the Conversation tab for what the endpoint
            returned.
          </Typography>
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          flexWrap: 'wrap',
        }}
      >
        <StatusChip
          status={status}
          label={STATUS_LABEL[status]}
          size="small"
          variant="filled"
        />
        <Typography variant="body2" color="text.secondary">
          {checksSummary(groups)}
        </Typography>
        {test.last_annotation && (
          <AnnotationIndicator
            verdict={annotationVerdict(test.last_annotation)}
            hasConflict={hasConflictingAnnotation(test)}
            annotator={test.last_annotation.user?.name}
            comment={test.last_annotation.comments}
          />
        )}
      </Box>

      <JudgedAgainst test={test} expectedResponse={expectedResponse} />

      {groups.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No checks were recorded for this test.
        </Typography>
      ) : (
        groups.map(group => (
          <CheckGroupCard
            key={group.key}
            group={group}
            test={test}
            turnCount={turnCount}
            annotations={metricAnnotations}
            onAnnotateMetric={onAnnotateMetric}
          />
        ))
      )}
    </Box>
  );
}

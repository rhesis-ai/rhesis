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
  Chip,
  Collapse,
  IconButton,
  Tooltip,
  Alert,
  AlertTitle,
  useTheme,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import RemoveIcon from '@mui/icons-material/Remove';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RateReviewIcon from '@mui/icons-material/RateReview';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { MetricsSource } from '@/utils/api-client/interfaces/test-configuration';
import StatusChip from '@/components/common/StatusChip';
import AnnotationIndicator from '@/components/annotations/AnnotationIndicator';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import { STATUS_LABEL } from '@/constants/outcomes';
import { getEndpointFailure } from '@/utils/endpoint-failure';
import {
  getEffectiveTestResultStatus,
  hasConflictingAnnotation,
  isPassedStatusName,
} from '@/utils/test-result-status';
import {
  buildResultChecks,
  checksSummary,
  countChecks,
  turnScopeLabel,
  type ResultCheck,
  type ResultCheckGroup,
} from '@/utils/result-checks';

interface TestDetailEvaluationTabProps {
  test: TestResultDetail;
  /** Source of metrics used in this test run */
  metricsSource?: MetricsSource | string;
  onAnnotateMetric?: (metricName: string) => void;
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

function VerdictIcon({ passed }: { passed: boolean | null }) {
  const theme = useTheme();
  const sx = { fontSize: theme.spacing(2.5), mt: 0.25, flexShrink: 0 };
  if (passed === null) {
    return <RemoveIcon aria-label="Not scored" color="disabled" sx={sx} />;
  }
  return passed ? (
    <CheckIcon aria-label="Passed" color="success" sx={sx} />
  ) : (
    <CloseIcon aria-label="Failed" color="error" sx={sx} />
  );
}

function scoreText(check: ResultCheck): string | undefined {
  const { score, threshold } = check.result ?? {};
  if (typeof score !== 'number' || typeof threshold !== 'number') {
    return undefined;
  }
  return `Score ${score.toFixed(2)} · threshold ${threshold.toFixed(2)}`;
}

function CheckRow({
  check,
  turnCount,
  actions,
}: {
  check: ResultCheck;
  turnCount?: number;
  actions?: React.ReactNode;
}) {
  const scope = turnScopeLabel(check.relevantTurns, turnCount);
  const score = scoreText(check);
  return (
    <Box sx={{ display: 'flex', gap: 1.5, px: 2.25, py: 1.5 }}>
      <VerdictIcon passed={check.passed} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 1,
          }}
        >
          <Typography variant="body2" fontWeight={500}>
            {check.label}
          </Typography>
          {scope && <Chip label={scope} size="small" variant="outlined" />}
          {check.passed === null && (
            <Chip label="Not scored" size="small" variant="outlined" />
          )}
          {score && (
            <Typography variant="caption" color="text.secondary">
              {score}
            </Typography>
          )}
          <Box sx={{ flexGrow: 1 }} />
          {actions}
        </Box>
        {check.reason && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 0.5, wordBreak: 'break-word' }}
          >
            {check.reason}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  const theme = useTheme();
  return (
    <Typography
      variant="caption"
      component="h4"
      color="text.secondary"
      sx={{
        display: 'block',
        px: 2.25,
        pt: 1.5,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: theme.typography.overline.letterSpacing,
      }}
    >
      {children}
    </Typography>
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

function CheckGroupCard({
  group,
  test,
  turnCount,
  annotations,
  onAnnotateMetric,
}: CheckGroupCardProps) {
  const { passed, total } = countChecks(group.checks);
  const groupMetric = group.metric
    ? test.test_metrics?.metrics?.[group.metric]
    : undefined;
  // Criteria split by kind; a group of whole metrics has no kind and stays one list.
  const hasKinds = group.checks.some(c => c.kind);
  const mustDo = group.checks.filter(c => c.kind !== 'prohibited');
  const mustNotDo = group.checks.filter(c => c.kind === 'prohibited');
  const showReasoning =
    !!groupMetric?.reason && group.checks.every(c => !c.result);

  const rowsFor = (checks: ResultCheck[]) =>
    checks.map(check => (
      <CheckRow
        key={check.key}
        check={check}
        turnCount={turnCount}
        actions={
          group.metric ? undefined : (
            <MetricActions
              metric={check.metric}
              annotation={annotations.get(check.metric)}
              overruled={!!check.result?.override}
              onAnnotateMetric={onAnnotateMetric}
            />
          )
        }
      />
    ));

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: BORDER_RADIUS.md,
        borderColor: 'divider',
        boxShadow: ELEVATION.xs,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.25,
          px: 2.25,
          py: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="subtitle1" component="h3" fontWeight={600}>
          {group.title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {`${passed} of ${total} passed`}
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        {group.metric && (
          <MetricActions
            metric={group.metric}
            annotation={annotations.get(group.metric)}
            overruled={!!groupMetric?.override}
            onAnnotateMetric={onAnnotateMetric}
          />
        )}
      </Box>
      {hasKinds ? (
        <>
          {mustDo.length > 0 && <SubHeading>Must do</SubHeading>}
          {rowsFor(mustDo)}
          {mustNotDo.length > 0 && <SubHeading>Must not do</SubHeading>}
          {rowsFor(mustNotDo)}
        </>
      ) : (
        rowsFor(group.checks)
      )}
      {showReasoning && groupMetric && (
        <Reasoning
          reason={groupMetric.reason}
          evidence={test.test_output?.goal_evaluation?.evidence ?? []}
        />
      )}
    </Paper>
  );
}

export default function TestDetailEvaluationTab({
  test,
  metricsSource,
  onAnnotateMetric,
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
            them against. See the Overview tab for what the endpoint returned.
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
        <Typography variant="body1" color="text.secondary">
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

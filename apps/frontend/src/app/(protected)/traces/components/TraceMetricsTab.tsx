'use client';

import {
  annotationsByMetric,
  annotationsByTurn,
} from '@/components/annotations/annotation-summary';
import type { AnnotationSummaryEntry } from '@/utils/api-client/interfaces/annotation';
import { useMemo, useState } from 'react';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { ChevronRightIcon, RateReviewIcon } from '@/components/icons';
import {
  SpanNode,
  TraceMetricsStatus,
  TRACE_METRICS_STATUS,
} from '@/utils/api-client/interfaces/telemetry';
import StatusChip from '@/components/common/StatusChip';
import { TEST_RESULT_STATUS_NAMES } from '@/utils/test-result-status';
import { allMetricsPassed } from '@/constants/outcomes';

interface MetricOverride {
  original_value: boolean;
  /** The annotation that overrode the metric. */
  annotation_id: string;
  overridden_by: string;
  overridden_at: string;
}

interface MetricEntry {
  name: string;
  is_successful?: boolean;
  score?: number;
  reason?: string;
  backend?: string;
  class_name?: string;
  threshold?: number;
  duration_ms?: number;
  description?: string;
  override?: MetricOverride;
}

interface MetricSection {
  execution_time?: number;
  metrics?: Record<string, MetricEntry>;
}

interface TraceMetricsTabProps {
  selectedSpan: SpanNode | null;
  isConversationTrace: boolean;
  onAnnotateMetric?: (metricName: string) => void;
  onAnnotateTurn?: (turnNumber: number, turnPassed?: boolean) => void;
  traceMetricsStatus?: TraceMetricsStatus | null;
  selectedTurnNumber?: number | null;
}

const COLUMN = { score: 14, result: 12, action: 4 } as const;

function passedChip(passed: boolean) {
  const name = passed
    ? TEST_RESULT_STATUS_NAMES.PASSED
    : TEST_RESULT_STATUS_NAMES.FAILED;
  return (
    <StatusChip status={name} label={name} size="small" variant="filled" />
  );
}

/** A 0–1 score as a short bar, with the threshold marked when there is one. */
function ScoreBar({ score, threshold }: { score: number; threshold?: number }) {
  return (
    <Box
      aria-hidden
      sx={{
        position: 'relative',
        width: theme => theme.spacing(7),
        height: theme => theme.spacing(0.75),
        borderRadius: theme => theme.spacing(0.5),
        bgcolor: 'action.hover',
        flexShrink: 0,
      }}
    >
      <Box
        sx={theme => ({
          position: 'absolute',
          inset: 0,
          right: 'auto',
          width: `${Math.min(Math.max(score, 0), 1) * 100}%`,
          borderRadius: theme.spacing(0.5),
          bgcolor:
            threshold === undefined || score >= threshold
              ? 'success.main'
              : 'error.main',
        })}
      />
      {threshold !== undefined && threshold >= 0 && threshold <= 1 && (
        <Box
          sx={theme => ({
            position: 'absolute',
            top: theme.spacing(-0.375),
            bottom: theme.spacing(-0.375),
            left: `${threshold * 100}%`,
            width: '2px',
            bgcolor: 'text.primary',
          })}
        />
      )}
    </Box>
  );
}

function MetricRow({
  name,
  metric,
  annotation,
  onAnnotate,
}: {
  name: string;
  metric: MetricEntry;
  annotation?: AnnotationSummaryEntry;
  onAnnotate?: () => void;
}) {
  const [open, setOpen] = useState(!metric.is_successful);
  const isOverruled = !!metric.override;
  const isConfirmed = !!annotation && !isOverruled;
  const hasScore = typeof metric.score === 'number';

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          minHeight: theme => theme.spacing(4.5),
          px: 1,
          '&:hover': { bgcolor: 'action.hover' },
        }}
      >
        <Box
          component="button"
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(o => !o)}
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            p: 0,
            border: 0,
            bgcolor: 'transparent',
            color: 'text.primary',
            cursor: 'pointer',
            textAlign: 'left',
            font: 'inherit',
          }}
        >
          <ChevronRightIcon
            sx={{
              fontSize: theme => theme.spacing(2),
              color: 'text.secondary',
              transform: open ? 'rotate(90deg)' : 'none',
              transition: 'transform 0.15s',
            }}
          />
          <Tooltip
            title={metric.description || ''}
            disableHoverListener={!metric.description}
            enterDelay={300}
          >
            <Typography variant="body2" noWrap>
              {name}
            </Typography>
          </Tooltip>
        </Box>
        <Box
          sx={{
            width: theme => theme.spacing(COLUMN.score),
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flexShrink: 0,
          }}
        >
          <Typography
            variant="caption"
            sx={theme => ({
              fontFamily: theme.typography.fontFamilyCode,
              width: theme.spacing(4.5),
            })}
          >
            {hasScore ? (metric.score as number).toFixed(2) : '—'}
          </Typography>
          {hasScore && (metric.score as number) <= 1 && (
            <ScoreBar
              score={metric.score as number}
              threshold={metric.threshold}
            />
          )}
        </Box>
        <Tooltip
          title={
            isOverruled
              ? `Annotated by ${annotation?.user?.name}: status changed to ${annotation?.status?.name}`
              : isConfirmed
                ? `Confirmed by ${annotation?.user?.name}`
                : ''
          }
          disableHoverListener={!annotation}
        >
          <Box
            sx={{ width: theme => theme.spacing(COLUMN.result), flexShrink: 0 }}
          >
            {passedChip(!!metric.is_successful)}
          </Box>
        </Tooltip>
        <Box
          sx={{ width: theme => theme.spacing(COLUMN.action), flexShrink: 0 }}
        >
          {onAnnotate && (
            <Tooltip title="Annotate this metric">
              <IconButton
                size="small"
                aria-label={`Annotate ${name}`}
                onClick={onAnnotate}
                sx={{ p: 0.5, color: 'text.secondary' }}
              >
                <RateReviewIcon sx={{ fontSize: theme => theme.spacing(2) }} />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>
      {open && (
        <Box
          sx={{
            pl: 4,
            pr: 1,
            pb: 1.25,
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
          }}
        >
          <Typography
            variant="body2"
            color={metric.reason ? 'text.primary' : 'text.disabled'}
            sx={{ wordBreak: 'break-word' }}
          >
            {metric.reason || 'No reason provided'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {[
              metric.threshold !== undefined && `Threshold ${metric.threshold}`,
              metric.backend,
              isOverruled &&
                annotation?.user?.name &&
                `Overruled by ${annotation.user.name}`,
              isConfirmed &&
                annotation?.user?.name &&
                `Confirmed by ${annotation.user.name}`,
            ]
              .filter(Boolean)
              .join(' · ')}
          </Typography>
        </Box>
      )}
    </Box>
  );
}

function MetricsList({
  metrics,
  annotations,
  onAnnotateMetric,
}: {
  metrics: Record<string, MetricEntry>;
  annotations: Map<string, AnnotationSummaryEntry>;
  onAnnotateMetric?: (metricName: string) => void;
}) {
  const entries = Object.entries(metrics);
  if (entries.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ py: 1 }}>
        No metrics recorded.
      </Typography>
    );
  }
  // Failures first: they are what the reader came for.
  entries.sort(
    ([, a], [, b]) => Number(!!a.is_successful) - Number(!!b.is_successful)
  );

  return (
    <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          px: 1,
          py: 0.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        {[
          { label: 'Metric', width: undefined },
          { label: 'Score', width: COLUMN.score },
          { label: 'Result', width: COLUMN.result },
          { label: '', width: COLUMN.action },
        ].map(col => (
          <Typography
            key={col.label || 'action'}
            variant="caption"
            color="text.secondary"
            sx={
              col.width
                ? { width: theme => theme.spacing(col.width), flexShrink: 0 }
                : { flex: 1, pl: 2.75 }
            }
          >
            {col.label}
          </Typography>
        ))}
      </Box>
      {entries.map(([name, metric]) => (
        <MetricRow
          key={name}
          name={name}
          metric={metric}
          annotation={annotations.get(name)}
          onAnnotate={
            onAnnotateMetric ? () => onAnnotateMetric(name) : undefined
          }
        />
      ))}
    </Box>
  );
}

function SectionHeader({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children?: React.ReactNode;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        minHeight: theme => theme.spacing(3.5),
        mb: 0.5,
      }}
    >
      <Typography
        variant="caption"
        component="h3"
        sx={{ fontWeight: 600, color: 'text.primary' }}
      >
        {title}
      </Typography>
      {note && (
        <Typography variant="caption" color="text.secondary">
          {note}
        </Typography>
      )}
      <Box sx={{ flex: 1 }} />
      {children}
    </Box>
  );
}

/**
 * The span's metric results, turn metrics first, as compact rows that open to
 * show the judge's reason. Failed metrics start open.
 */
export default function TraceMetricsTab({
  selectedSpan,
  isConversationTrace,
  onAnnotateMetric,
  onAnnotateTurn,
  traceMetricsStatus,
  selectedTurnNumber = null,
}: TraceMetricsTabProps) {
  const traceMetrics = selectedSpan?.trace_metrics as
    | Record<string, unknown>
    | undefined;
  const turnMetrics = traceMetrics?.turn_metrics as MetricSection | undefined;
  const conversationMetrics = traceMetrics?.conversation_metrics as
    | MetricSection
    | undefined;

  const metricAnnotationMap = useMemo(
    () => annotationsByMetric(selectedSpan?.annotation_summary),
    [selectedSpan?.annotation_summary]
  );
  const turnAnnotationMap = useMemo(
    () => annotationsByTurn(selectedSpan?.annotation_summary),
    [selectedSpan?.annotation_summary]
  );

  if (!turnMetrics?.metrics && !conversationMetrics?.metrics) {
    return (
      <Typography variant="caption" color="text.secondary">
        No trace metrics for this span.
      </Typography>
    );
  }

  // Per-turn, finer than anything the backend stores an outcome for -- see allMetricsPassed.
  const automatedTurnSuccess =
    turnMetrics?.metrics && Object.keys(turnMetrics.metrics).length > 0
      ? allMetricsPassed(Object.values(turnMetrics.metrics))
      : undefined;
  const turnOverride =
    selectedTurnNumber != null
      ? (
          traceMetrics?.turn_overrides as
            | Record<string, { success?: boolean; override?: MetricOverride }>
            | undefined
        )?.[String(selectedTurnNumber)]
      : undefined;
  const turnSuccess =
    turnOverride?.override && typeof turnOverride.success === 'boolean'
      ? turnOverride.success
      : (automatedTurnSuccess ?? false);
  const turnAnnotation =
    selectedTurnNumber != null
      ? turnAnnotationMap.get(selectedTurnNumber)
      : undefined;
  const showTurnVerdict = isConversationTrace && selectedTurnNumber != null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {traceMetricsStatus === TRACE_METRICS_STATUS.ERROR && (
        <Typography
          variant="caption"
          sx={theme => ({
            color: 'error.main',
            bgcolor: alpha(theme.palette.error.main, 0.08),
            px: 1.5,
            py: 1,
            borderRadius: theme.spacing(0.75),
          })}
        >
          Metric evaluation errored for this trace; results may be incomplete.
        </Typography>
      )}

      {turnMetrics?.metrics && (
        <Box>
          <SectionHeader
            title={
              showTurnVerdict
                ? `Turn ${selectedTurnNumber} metrics`
                : 'Turn metrics'
            }
          >
            {showTurnVerdict && (
              <>
                <Tooltip
                  title={
                    turnOverride?.override
                      ? `Annotated by ${turnAnnotation?.user?.name}: status changed to ${turnAnnotation?.status?.name}`
                      : turnAnnotation
                        ? `Confirmed by ${turnAnnotation.user?.name}`
                        : ''
                  }
                  disableHoverListener={!turnAnnotation}
                >
                  <Box>{passedChip(turnSuccess)}</Box>
                </Tooltip>
                {onAnnotateTurn && (
                  <Tooltip title="Annotate this turn">
                    <IconButton
                      size="small"
                      aria-label={`Annotate turn ${selectedTurnNumber}`}
                      onClick={() =>
                        onAnnotateTurn(
                          selectedTurnNumber as number,
                          turnSuccess
                        )
                      }
                      sx={{ p: 0.5, color: 'text.secondary' }}
                    >
                      <RateReviewIcon
                        sx={{ fontSize: theme => theme.spacing(2) }}
                      />
                    </IconButton>
                  </Tooltip>
                )}
              </>
            )}
          </SectionHeader>
          <MetricsList
            metrics={turnMetrics.metrics}
            annotations={metricAnnotationMap}
            onAnnotateMetric={onAnnotateMetric}
          />
        </Box>
      )}

      {isConversationTrace && conversationMetrics?.metrics && (
        <Box>
          <SectionHeader
            title="Conversation metrics"
            note="· shared across all turns"
          />
          <MetricsList
            metrics={conversationMetrics.metrics}
            annotations={metricAnnotationMap}
            onAnnotateMetric={onAnnotateMetric}
          />
        </Box>
      )}
    </Box>
  );
}

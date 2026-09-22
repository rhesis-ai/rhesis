'use client';

import React, { useMemo } from 'react';
import { Box, Chip, Stack, Typography } from '@mui/material';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import StatusChip from '@/components/common/StatusChip';
import AnnotationDrawer from '@/components/annotations/AnnotationDrawer';
import { allMetricsPassed, displayStatusOf } from '@/constants/outcomes';
import {
  ANNOTATION_ENTITY_TYPES,
  ANNOTATION_TARGET_LABELS,
  type AnnotationTargetType,
} from '@/utils/api-client/interfaces/annotation';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import type {
  InferredTarget,
  MentionOption,
} from '@/components/common/MentionTextInput';

interface TraceAnnotationDrawerProps {
  open: boolean;
  onClose: () => void;
  selectedSpan: SpanNode | null;
  onSave: () => Promise<void>;
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
}

interface MetricEntry {
  is_successful?: boolean;
  score?: number;
}

/** Both metric sections flattened, since a mention names a metric not a section. */
function allTraceMetrics(
  traceMetrics: Record<string, unknown> | null | undefined
): Record<string, MetricEntry> {
  if (!traceMetrics) return {};
  const result: Record<string, MetricEntry> = {};
  for (const section of ['turn_metrics', 'conversation_metrics']) {
    const sectionData = traceMetrics[section] as
      Record<string, unknown> | undefined;
    Object.assign(
      result,
      (sectionData?.metrics ?? {}) as Record<string, MetricEntry>
    );
  }
  return result;
}

/**
 * Annotating a trace span, with the automated verdict for whatever the comment
 * targets shown above the picker.
 *
 * Only that context block is trace-specific; the form itself is the shared
 * AnnotationDrawer.
 */
export default function TraceAnnotationDrawer({
  open,
  onClose,
  selectedSpan,
  onSave,
  initialComment,
  initialStatus,
  mentionableMetrics = [],
  mentionableTurns = [],
}: TraceAnnotationDrawerProps) {
  const metrics = useMemo(
    () =>
      allTraceMetrics(
        selectedSpan?.trace_metrics as Record<string, unknown> | undefined
      ),
    [selectedSpan]
  );

  /** The automated verdict for one target, which is what an annotation argues with. */
  const automatedStatusFor = (target: InferredTarget): 'passed' | 'failed' => {
    if (!selectedSpan) return 'failed';

    if (target.type === 'turn') {
      const traceMetrics = selectedSpan.trace_metrics as
        Record<string, unknown> | undefined;
      const turnSection = traceMetrics?.turn_metrics as
        Record<string, unknown> | undefined;
      const turnMetrics = turnSection?.metrics as
        Record<string, { is_successful?: boolean }> | undefined;
      // Per-turn: finer than anything the backend records an outcome for.
      return turnMetrics && Object.keys(turnMetrics).length > 0
        ? allMetricsPassed(Object.values(turnMetrics))
          ? 'passed'
          : 'failed'
        : 'failed';
    }

    if (target.type === 'metric' && target.reference) {
      return metrics[target.reference]?.is_successful ? 'passed' : 'failed';
    }

    // Whole-span target: the backend has already classified this span, so
    // there is nothing to re-derive.
    return displayStatusOf(selectedSpan) === 'Pass' ? 'passed' : 'failed';
  };

  const metricValues = Object.values(metrics);
  const passedCount = metricValues.filter(m => m.is_successful).length;

  const renderContext = (target: InferredTarget) => {
    const automated = automatedStatusFor(target);
    const label =
      ANNOTATION_TARGET_LABELS[target.type as AnnotationTargetType] ?? 'Trace';

    return (
      <Stack spacing={3}>
        <Box>
          <Typography
            variant="body2"
            gutterBottom
            sx={theme => ({ fontWeight: theme.typography.fontWeightMedium })}
          >
            Annotation Target
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <Chip
              icon={<TrackChangesIcon />}
              label={target.reference ? `${label}: ${target.reference}` : label}
              size="small"
              color={
                target.type === 'metric'
                  ? 'secondary'
                  : target.type === 'turn'
                    ? 'info'
                    : 'default'
              }
              variant="outlined"
            />
          </Box>
        </Box>

        <Box>
          <Typography
            variant="body2"
            gutterBottom
            sx={theme => ({ fontWeight: theme.typography.fontWeightMedium })}
          >
            Current Automated Status
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <StatusChip
              passed={automated === 'passed'}
              label={automated === 'passed' ? 'Passed' : 'Failed'}
              size="small"
              variant="filled"
            />
            {target.type === 'trace' && (
              <Typography variant="body2" color="text.secondary">
                {passedCount}/{metricValues.length} metrics passed
              </Typography>
            )}
            {target.type === 'metric' && target.reference && (
              <Typography variant="body2" color="text.secondary">
                Score: {metrics[target.reference]?.score ?? 'N/A'}
              </Typography>
            )}
            {target.type === 'turn' && (
              <Typography variant="body2" color="text.secondary">
                Based on turn metrics ({passedCount}/{metricValues.length}{' '}
                passed)
              </Typography>
            )}
          </Box>
        </Box>
      </Stack>
    );
  };

  return (
    <AnnotationDrawer
      open={open}
      onClose={onClose}
      entityType={ANNOTATION_ENTITY_TYPES.TRACE}
      entityId={selectedSpan?.id}
      onSaved={onSave}
      initialComment={initialComment}
      initialStatus={initialStatus}
      mentionableMetrics={mentionableMetrics}
      mentionableTurns={mentionableTurns}
      renderContext={renderContext}
    />
  );
}

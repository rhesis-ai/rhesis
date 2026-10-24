'use client';

import { Box } from '@mui/material';
import type { MentionOption } from '@/components/common/MentionTextInput';
import type {
  SpanNode,
  TraceDetailResponse,
  TraceMetricsStatus,
} from '@/utils/api-client/interfaces/telemetry';
import EvaluationVerdict from './EvaluationVerdict';
import TraceMetricsTab from './TraceMetricsTab';
import TestResultTab from './TestResultTab';
import TraceAnnotationsTab from './TraceAnnotationsTab';

interface EvaluationTabProps {
  span: SpanNode;
  trace: TraceDetailResponse;
  hasTraceMetrics: boolean;
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

/**
 * Everything that judges the span in one place: the automated and human
 * verdicts, the metric results, the test it ran for, and the annotations.
 */
export default function EvaluationTab({
  span,
  trace,
  hasTraceMetrics,
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
  return (
    <Box
      sx={{
        px: 2,
        py: 1.5,
        display: 'flex',
        flexDirection: 'column',
        gap: 2.5,
      }}
    >
      <EvaluationVerdict
        span={span}
        onAnnotate={onAnnotateTrace}
        onChanged={onTraceUpdated}
      />

      {hasTraceMetrics && (
        <TraceMetricsTab
          selectedSpan={span}
          isConversationTrace={isConversationTrace}
          onAnnotateMetric={onAnnotateMetric}
          onAnnotateTurn={onAnnotateTurn}
          traceMetricsStatus={traceMetricsStatus}
          selectedTurnNumber={selectedTurnNumber}
        />
      )}

      {trace.test_result && (
        <TestResultTab trace={trace} showMetrics={!hasTraceMetrics} />
      )}

      <TraceAnnotationsTab
        selectedSpan={span}
        trace={trace}
        onTraceUpdated={onTraceUpdated}
        mentionableMetrics={mentionableMetrics}
        mentionableTurns={mentionableTurns}
        compact
      />
    </Box>
  );
}

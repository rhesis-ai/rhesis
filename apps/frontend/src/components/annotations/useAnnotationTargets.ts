import { useMemo } from 'react';
import {
  toMentionId,
  type MentionOption,
} from '@/components/common/MentionTextInput';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';

/**
 * What a comment can @mention, which is what decides an annotation's target.
 *
 * Where the names come from is entity-specific, so there are two entry points;
 * the mapping into mention options is shared, and so is walking a span's two
 * metric sections.
 */
export interface AnnotationTargets {
  metrics: MentionOption[];
  turns: MentionOption[];
}

function metricOptions(names: string[]): MentionOption[] {
  return names.map(name => ({
    id: toMentionId(name),
    display: name,
    type: 'metric' as const,
  }));
}

function turnOptions(turnNumbers: number[]): MentionOption[] {
  return turnNumbers.map(turn => ({
    id: String(turn),
    display: `Turn ${turn}`,
    type: 'turn' as const,
  }));
}

/** Every metric named on a span, across both sections. */
export function spanMetricNames(
  traceMetrics: Record<string, unknown> | null | undefined
): string[] {
  if (!traceMetrics) return [];
  const names: string[] = [];
  for (const section of ['turn_metrics', 'conversation_metrics']) {
    const sectionData = traceMetrics[section] as
      | Record<string, unknown>
      | undefined;
    const metrics = sectionData?.metrics as Record<string, unknown> | undefined;
    if (metrics) names.push(...Object.keys(metrics));
  }
  return names;
}

/** Mentionable targets on a test result: its metrics and its conversation turns. */
export function useTestResultAnnotationTargets(
  test: TestResultDetail | null | undefined,
  conversationTest?: TestResultDetail | null
): AnnotationTargets {
  const metrics = useMemo(
    () => metricOptions(Object.keys(test?.test_metrics?.metrics ?? {})),
    [test]
  );

  const turns = useMemo(() => {
    const summary = conversationTest?.test_output?.conversation_summary;
    if (!Array.isArray(summary)) return [];
    return turnOptions(summary.map((turn: { turn: number }) => turn.turn));
  }, [conversationTest]);

  return { metrics, turns };
}

/** Mentionable targets on a trace span: its metrics and the trace's turns. */
export function useTraceAnnotationTargets(
  selectedSpan: SpanNode | null | undefined,
  trace: TraceDetailResponse | null | undefined
): AnnotationTargets {
  const metrics = useMemo(
    () =>
      metricOptions(
        spanMetricNames(
          selectedSpan?.trace_metrics as Record<string, unknown> | undefined
        )
      ),
    [selectedSpan]
  );

  const turns = useMemo(() => {
    if (!trace?.root_spans || !trace.conversation_id) return [];
    // A turn is a root span that carried conversation text, numbered in order.
    const conversational = trace.root_spans.filter(
      span =>
        span.attributes['rhesis.conversation.input'] ||
        span.attributes['rhesis.conversation.output']
    );
    return turnOptions(conversational.map((_, i) => i + 1));
  }, [trace]);

  return { metrics, turns };
}

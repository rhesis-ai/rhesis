import type { TelemetryClient } from '@/utils/api-client/telemetry-client';
import type {
  SpanNode,
  TraceDetailResponse,
  TraceQueryParams,
} from '@/utils/api-client/interfaces/telemetry';
import {
  conversationRootSpans,
  type TurnTraceTarget,
} from '@/utils/conversation-from-spans';

export interface ConversationTurns {
  /** Turn n's root span is entry n-1. */
  spans: SpanNode[];
  targets: TurnTraceTarget[];
}

export type ConversationTraceQuery = Pick<
  TraceQueryParams,
  'test_result_id' | 'conversation_id' | 'project_id'
>;

/**
 * Which traces make up a trace's conversation, or null for a trace that has none. A test
 * result is asked first: on traces stored before the backend linked them, turn 1 carries no
 * conversation_id, so asking by conversation_id would drop it.
 */
export function conversationTraceQuery(
  trace: TraceDetailResponse
): ConversationTraceQuery | null {
  if (!trace.conversation_id) return null;
  if (trace.test_result?.id) return { test_result_id: trace.test_result.id };
  return {
    conversation_id: trace.conversation_id,
    project_id: trace.project?.id,
  };
}

/**
 * A conversation's turns as root spans, from its traces in start order. Covers one trace per
 * turn and one trace holding every turn. `known` is reused rather than fetched again.
 */
export async function loadConversationTurns(
  client: TelemetryClient,
  query: ConversationTraceQuery,
  known?: TraceDetailResponse
): Promise<ConversationTurns> {
  const response = await client.listTraces({ ...query, limit: 100 });
  const traces = [...response.traces].sort(
    (a, b) =>
      new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
  );
  const details = await Promise.all(
    traces.map(trace =>
      trace.trace_id === known?.trace_id
        ? known
        : client.getTrace(trace.trace_id, trace.project_id)
    )
  );
  return conversationRootSpans(
    traces.map((trace, i) => ({
      traceId: trace.trace_id,
      projectId: trace.project_id,
      rootSpans: details[i].root_spans ?? [],
    }))
  );
}

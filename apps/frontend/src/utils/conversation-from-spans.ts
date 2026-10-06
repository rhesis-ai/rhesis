import type { FileResponse } from '@/utils/api-client/interfaces/file';
import type { ConversationMessage } from '@/utils/api-client/interfaces/tests';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import type {
  ConversationTurn,
  MetricResult,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';

/**
 * A trace's turn and conversation metrics in one map, as ConversationHistory takes them. The
 * conversation ones win on a name clash, as in the trace metrics tab.
 */
export function traceMetricsFromSpans(
  rootSpans: SpanNode[]
): Record<string, MetricResult> {
  const traceMetrics = rootSpans.find(s => s.trace_metrics)?.trace_metrics as
    | Record<string, { metrics?: Record<string, MetricResult> } | undefined>
    | undefined;
  return {
    ...(traceMetrics?.turn_metrics?.metrics ?? {}),
    ...(traceMetrics?.conversation_metrics?.metrics ?? {}),
  };
}

/**
 * Whether this test result is a multi-turn conversation (test-set type or
 * per-result output shape).
 */
export function isMultiTurnTestResult(
  test: TestResultDetail,
  testSetType?: string
): boolean {
  if (testSetType?.toLowerCase().includes('multi-turn')) return true;
  if ((test.test_output?.conversation_summary?.length ?? 0) > 0) return true;
  if (test.test_output?.goal_evaluation) return true;
  if (test.test_output?.test_configuration?.goal) return true;
  return false;
}

/**
 * Reconstruct conversation turns from trace span attributes when
 * test_output.conversation_summary is missing (same fallback as traces UI).
 */
export function reconstructConversationFromSpans(
  rootSpans: SpanNode[]
): ConversationTurn[] {
  return rootSpans
    .filter(
      span =>
        span.attributes['rhesis.conversation.input'] ||
        span.attributes['rhesis.conversation.output']
    )
    .map((span, i) => ({
      turn: i + 1,
      timestamp: span.start_time,
      penelope_message: String(
        span.attributes['rhesis.conversation.input'] || ''
      ),
      target_response: String(
        span.attributes['rhesis.conversation.output'] || ''
      ),
      penelope_reasoning: '',
      session_id: span.span_id,
      // Whether the call itself went through; metric verdicts reach the turns as findings.
      success: span.status_code !== 'ERROR',
    }));
}

export function mergeSpanFilesIntoConversation(
  conversation: ConversationTurn[],
  spanFiles: FileResponse[][]
): ConversationTurn[] {
  if (spanFiles.length === 0) return conversation;
  return conversation.map((turn, i) => ({
    ...turn,
    penelope_files: spanFiles[i] ?? [],
  }));
}

/**
 * Resolve conversation turns for a test result: prefer stored summary, else spans.
 */
export function resolveConversationSummary(
  test: TestResultDetail,
  rootSpans: SpanNode[],
  spanFiles: FileResponse[][]
): ConversationTurn[] {
  const stored = test.test_output?.conversation_summary ?? [];
  const base =
    stored.length > 0 ? stored : reconstructConversationFromSpans(rootSpans);
  return mergeSpanFilesIntoConversation(base, spanFiles);
}

/**
 * A turn as the user/assistant pair the test-extraction endpoint takes. Empty sides are
 * dropped, so a turn that errored before the target replied still yields its user message.
 */
export function turnToMessages(turn: ConversationTurn): ConversationMessage[] {
  const messages: ConversationMessage[] = [];
  if (turn.penelope_message?.trim()) {
    messages.push({ role: 'user', content: turn.penelope_message });
  }
  if (turn.target_response?.trim()) {
    messages.push({ role: 'assistant', content: turn.target_response });
  }
  return messages;
}

/** Every turn of a conversation, in order, as extraction-endpoint messages. */
export function conversationToMessages(
  turns: ConversationTurn[]
): ConversationMessage[] {
  return turns.flatMap(turnToMessages);
}

import type { FileResponse } from '@/utils/api-client/interfaces/file';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import type {
  ConversationTurn,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';

function getAutomatedTurnSuccess(rootSpans: SpanNode[]): boolean | undefined {
  const traceMetrics = rootSpans.find(s => s.trace_metrics)?.trace_metrics as
    Record<string, unknown> | undefined;
  if (!traceMetrics) return undefined;

  const turnSection = traceMetrics.turn_metrics as
    Record<string, unknown> | undefined;
  if (!turnSection) return undefined;

  const metrics = turnSection.metrics as
    Record<string, { is_successful?: boolean }> | undefined;
  if (metrics && Object.keys(metrics).length > 0) {
    return Object.values(metrics).every(m => m?.is_successful);
  }

  return undefined;
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
  const automatedSuccess = getAutomatedTurnSuccess(rootSpans);

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
      success: automatedSuccess ?? span.status_code !== 'ERROR',
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

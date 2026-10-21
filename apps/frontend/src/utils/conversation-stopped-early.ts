/**
 * Why Penelope stopped a multi-turn conversation before it finished.
 *
 * Mirrors `is_unfinished_conversation` in
 * `apps/backend/src/rhesis/backend/app/utils/response_extractor.py`, which is what makes
 * the backend record such a run as Error without scoring it. Keep the two in step.
 */

import type { TestOutput } from '@/utils/api-client/interfaces/test-results';

// Penelope's findings that say why it gave up; the rest summarise the run.
const STOP_REASON_PREFIXES = [
  'Workflow validation blocked execution:',
  'Error:',
];

/** The stop reason, or undefined when the conversation ran to its end. */
export function getConversationStopReason(
  testOutput: TestOutput | undefined
): string | undefined {
  if (
    testOutput?.status !== 'error' ||
    !Array.isArray(testOutput.conversation_summary)
  ) {
    return undefined;
  }
  const reason = (testOutput.findings ?? []).find(
    finding =>
      typeof finding === 'string' &&
      STOP_REASON_PREFIXES.some(prefix => finding.startsWith(prefix))
  );
  return reason ?? 'Penelope could not finish the conversation.';
}

import { getConversationStopReason } from '../conversation-stopped-early';
import type { TestOutput } from '@/utils/api-client/interfaces/test-results';

const BLOCKED =
  'Workflow validation blocked execution: Tool analyze_response used repeatedly.';

describe('getConversationStopReason', () => {
  it('returns the finding that says why Penelope stopped', () => {
    const output: TestOutput = {
      status: 'error',
      conversation_summary: [],
      findings: [
        '✓ All criteria met (4/4)',
        'Test completed in 4 turn(s)',
        BLOCKED,
      ],
    };
    expect(getConversationStopReason(output)).toBe(BLOCKED);
  });

  it('falls back to a generic reason when no finding names one', () => {
    const output: TestOutput = {
      status: 'error',
      conversation_summary: [],
      findings: ['Test completed in 2 turn(s)'],
    };
    expect(getConversationStopReason(output)).toBe(
      'Penelope could not finish the conversation.'
    );
  });

  it('ignores a conversation that ran to its end', () => {
    const output: TestOutput = {
      status: 'max_turns',
      conversation_summary: [],
      findings: [BLOCKED],
    };
    expect(getConversationStopReason(output)).toBeUndefined();
  });

  it('ignores a single-turn output with its own status field', () => {
    expect(
      getConversationStopReason({ status: 'error', output: 'hi' })
    ).toBeUndefined();
  });
});

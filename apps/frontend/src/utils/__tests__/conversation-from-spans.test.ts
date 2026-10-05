import {
  conversationToMessages,
  reconstructConversationFromSpans,
  traceMetricsFromSpans,
  turnToMessages,
} from '@/utils/conversation-from-spans';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

const span = (overrides: Partial<SpanNode>): SpanNode =>
  ({
    span_id: 's',
    start_time: '2026-09-29T10:00:00Z',
    status_code: 'OK',
    attributes: {
      'rhesis.conversation.input': 'hi',
      'rhesis.conversation.output': 'hello',
    },
    ...overrides,
  }) as unknown as SpanNode;

describe('conversation from spans', () => {
  const failedMetric = {
    turn_metrics: { metrics: { Tone: { is_successful: false } } },
    conversation_metrics: {
      metrics: { 'Red Flag Escalation': { is_successful: false } },
    },
  };

  it('marks a turn unsuccessful only when its own call failed', () => {
    const turns = reconstructConversationFromSpans([
      span({ trace_metrics: failedMetric } as Partial<SpanNode>),
      span({ status_code: 'ERROR' }),
    ]);
    expect(turns.map(t => t.success)).toEqual([true, false]);
  });

  it('returns turn and conversation metrics together', () => {
    const metrics = traceMetricsFromSpans([
      span({ trace_metrics: failedMetric } as Partial<SpanNode>),
    ]);
    expect(Object.keys(metrics)).toEqual(['Tone', 'Red Flag Escalation']);
  });
});

describe('conversation to extraction messages', () => {
  const turns = reconstructConversationFromSpans([
    span({
      attributes: {
        'rhesis.conversation.input': 'Berlin to Paris?',
        'rhesis.conversation.output': 'Try Air France.',
      },
    } as Partial<SpanNode>),
    span({
      attributes: { 'rhesis.conversation.input': 'And to New York?' },
    } as Partial<SpanNode>),
  ]);

  it('pairs each turn as a user then assistant message', () => {
    expect(turnToMessages(turns[0])).toEqual([
      { role: 'user', content: 'Berlin to Paris?' },
      { role: 'assistant', content: 'Try Air France.' },
    ]);
  });

  it('drops the side of a turn that has no text', () => {
    expect(turnToMessages(turns[1])).toEqual([
      { role: 'user', content: 'And to New York?' },
    ]);
  });

  it('keeps every turn in order for the whole conversation', () => {
    expect(conversationToMessages(turns).map(m => m.content)).toEqual([
      'Berlin to Paris?',
      'Try Air France.',
      'And to New York?',
    ]);
  });
});

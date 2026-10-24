import { extractSpanIO, groupAttributes } from '../span-io';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

function span(overrides: Partial<SpanNode>): SpanNode {
  return {
    id: 'id',
    span_id: 'span',
    span_name: 'function.run',
    span_kind: 'INTERNAL',
    span_type: 'function',
    start_time: '2026-01-01T00:00:00Z',
    end_time: '2026-01-01T00:00:01Z',
    duration_ms: 1000,
    status_code: 'OK',
    attributes: {},
    events: [],
    children: [],
    ...overrides,
  } as SpanNode;
}

describe('extractSpanIO', () => {
  it('drops empty positional args and parses keyword args', () => {
    const [io] = extractSpanIO(
      span({
        attributes: {
          'function.args': '[]',
          'function.kwargs': '{"message":"hi"}',
          'function.result': 'hello',
        },
      })
    );
    expect(io.kind).toBe('function');
    expect(io.input).toEqual([{ label: undefined, value: { message: 'hi' } }]);
    expect(io.output).toBe('hello');
  });

  it('labels positional and keyword args when both are present', () => {
    const [io] = extractSpanIO(
      span({
        attributes: {
          'function.args': '["a"]',
          'function.kwargs': '{"b":1}',
        },
      })
    );
    expect(io.input.map(i => i.label)).toEqual(['Positional', 'Keyword']);
    expect(io.output).toBeNull();
  });

  it('reads LLM prompts and completion from events', () => {
    const [io] = extractSpanIO(
      span({
        events: [
          {
            name: 'ai.prompt',
            timestamp: '1',
            attributes: {
              'ai.prompt.role': 'system',
              'ai.prompt.content': 'Be brief',
            },
          },
          {
            name: 'ai.prompt',
            timestamp: '2',
            attributes: { 'ai.prompt.role': 'user', 'ai.prompt.content': 'Hi' },
          },
          {
            name: 'ai.completion',
            timestamp: '3',
            attributes: { 'ai.completion.content': 'Hello' },
          },
        ],
      } as Partial<SpanNode>)
    );
    expect(io.kind).toBe('llm');
    expect(io.messages).toEqual([
      { role: 'system', content: 'Be brief' },
      { role: 'user', content: 'Hi' },
    ]);
    expect(io.output).toBe('Hello');
  });

  it('returns nothing for a span without I/O', () => {
    expect(extractSpanIO(span({}))).toEqual([]);
  });
});

describe('groupAttributes', () => {
  it('sorts attributes by prefix and leaves out the ones shown as I/O', () => {
    const groups = groupAttributes({
      'ai.model.name': 'gpt',
      'ai.llm.tokens.input': 10,
      'function.name': 'run',
      'function.kwargs': '{}',
      'rhesis.test.id': 't1',
      'service.name': 'svc',
      'endpoint.version_info': '{"prompt_version":"v1"}',
    });
    expect(groups.llm).toEqual({ 'ai.model.name': 'gpt' });
    expect(groups.function).toEqual({ 'function.name': 'run' });
    expect(groups.test).toEqual({ 'rhesis.test.id': 't1' });
    expect(groups.other).toEqual({ 'service.name': 'svc' });
    expect(groups.versionInfo).toEqual({ prompt_version: 'v1' });
  });
});

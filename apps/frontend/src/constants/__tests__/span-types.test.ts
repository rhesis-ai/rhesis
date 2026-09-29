import CodeIcon from '@mui/icons-material/Code';
import {
  getSpanTypeInfo,
  SPAN_TYPES,
  spanTypeLabel,
} from '@/constants/span-types';

describe('span types', () => {
  it('labels every span type the backend writes', () => {
    // Trace.span_type: ai.operation.type values, plus the generic "span".
    const expected: Record<string, string> = {
      'llm.invoke': 'LLM call',
      'tool.invoke': 'Tool',
      'agent.invoke': 'Agent',
      'agent.handoff': 'Agent handoff',
      retrieval: 'Retrieval',
      'embedding.create': 'Embedding',
      rerank: 'Rerank',
      evaluation: 'Evaluation',
      guardrail: 'Guardrail',
      transform: 'Transform',
      span: 'Span',
    };

    for (const [type, label] of Object.entries(expected)) {
      expect(spanTypeLabel(type)).toBe(label);
    }
    expect(Object.keys(SPAN_TYPES).sort()).toEqual(
      Object.keys(expected).sort()
    );
  });

  it('keeps the raw key for a type it does not know', () => {
    const info = getSpanTypeInfo('chain');

    expect(info.label).toBe('chain');
    expect(info.icon).toBe(CodeIcon);
    expect(info.color).toBe('text.secondary');
  });

  it('does not mistake object built-ins for span types', () => {
    expect(spanTypeLabel('toString')).toBe('toString');
  });

  it('treats a missing type as a generic span', () => {
    expect(getSpanTypeInfo(undefined)).toBe(SPAN_TYPES.span);
    expect(getSpanTypeInfo(null)).toBe(SPAN_TYPES.span);
    expect(spanTypeLabel('')).toBe('Span');
  });
});

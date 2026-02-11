import { getSpanColor } from '../span-icon-mapper';
import { SEMANTIC_LAYER_COLORS } from '@/constants/semantic-layer-icons';

// getSpanIcon returns React components which are harder to assert on,
// so we focus on getSpanColor which returns string values.

describe('getSpanColor', () => {
  it('returns error color when statusCode is ERROR', () => {
    expect(getSpanColor('ai.llm.invoke', 'ERROR')).toBe(
      SEMANTIC_LAYER_COLORS.error
    );
    expect(getSpanColor('unknown.span', 'ERROR')).toBe(
      SEMANTIC_LAYER_COLORS.error
    );
  });

  it('returns exact match color for known span names', () => {
    expect(getSpanColor('ai.llm.invoke', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.llm.invoke']
    );
    expect(getSpanColor('ai.tool.invoke', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.tool.invoke']
    );
    expect(getSpanColor('ai.retrieval', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.retrieval']
    );
    expect(getSpanColor('ai.embedding', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.embedding']
    );
    expect(getSpanColor('ai.agent.invoke', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.agent.invoke']
    );
    expect(getSpanColor('ai.agent.handoff', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.agent.handoff']
    );
  });

  it('returns pattern match color for spans containing known patterns', () => {
    // "function." pattern
    expect(getSpanColor('function.calculate', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['function.']
    );
    // "db." pattern
    expect(getSpanColor('db.query.select', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['db.']
    );
    // "http." pattern
    expect(getSpanColor('http.request.get', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['http.']
    );
  });

  it('returns default color for unknown span names', () => {
    expect(getSpanColor('unknown.span', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS.default
    );
    expect(getSpanColor('custom.operation', 'OK')).toBe(
      SEMANTIC_LAYER_COLORS.default
    );
  });

  it('prioritizes error status over span name', () => {
    // Even for a known span, ERROR should take priority
    expect(getSpanColor('ai.retrieval', 'ERROR')).toBe(
      SEMANTIC_LAYER_COLORS.error
    );
  });

  it('handles empty span name', () => {
    expect(getSpanColor('', 'OK')).toBe(SEMANTIC_LAYER_COLORS.default);
  });
});

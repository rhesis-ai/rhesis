import FunctionsIcon from '@mui/icons-material/Functions';
import ShieldIcon from '@mui/icons-material/Shield';
import { getSpanColor, getSpanIcon } from '../span-icon-mapper';
import { SEMANTIC_LAYER_COLORS } from '@/constants/semantic-layer-icons';
import { SPAN_TYPES } from '@/constants/span-types';

/** A span with only a name, as the name-prefix fallback sees it. */
const named = (span_name: string) => ({ span_name });

describe('getSpanColor', () => {
  it('returns error color when statusCode is ERROR', () => {
    expect(getSpanColor(named('ai.llm.invoke'), 'ERROR')).toBe(
      SEMANTIC_LAYER_COLORS.error
    );
    expect(getSpanColor(named('unknown.span'), 'ERROR')).toBe(
      SEMANTIC_LAYER_COLORS.error
    );
    expect(
      getSpanColor({ span_name: 'x', span_type: 'tool.invoke' }, 'ERROR')
    ).toBe(SEMANTIC_LAYER_COLORS.error);
  });

  it('colours by span_type when the span has a specific one', () => {
    // The name says nothing; the type decides.
    expect(
      getSpanColor({ span_name: 'my_tool', span_type: 'tool.invoke' }, 'OK')
    ).toBe(SPAN_TYPES['tool.invoke'].color);
    expect(
      getSpanColor({ span_name: 'check', span_type: 'guardrail' }, 'OK')
    ).toBe(SPAN_TYPES.guardrail.color);
  });

  it('falls back to the span name for generic spans', () => {
    expect(
      getSpanColor(
        { span_name: 'function.haystack.pipeline.run', span_type: 'span' },
        'OK'
      )
    ).toBe(SEMANTIC_LAYER_COLORS['function.']);
    expect(
      getSpanColor({ span_name: 'db.query', span_type: 'span' }, 'OK')
    ).toBe(SEMANTIC_LAYER_COLORS['db.']);
  });

  it('returns exact match color for known span names', () => {
    expect(getSpanColor(named('ai.llm.invoke'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.llm.invoke']
    );
    expect(getSpanColor(named('ai.tool.invoke'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.tool.invoke']
    );
    expect(getSpanColor(named('ai.retrieval'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.retrieval']
    );
    expect(getSpanColor(named('ai.embedding'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.embedding']
    );
    expect(getSpanColor(named('ai.agent.invoke'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.agent.invoke']
    );
    expect(getSpanColor(named('ai.agent.handoff'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['ai.agent.handoff']
    );
  });

  it('returns pattern match color for spans containing known patterns', () => {
    expect(getSpanColor(named('function.calculate'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['function.']
    );
    expect(getSpanColor(named('db.query.select'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['db.']
    );
    expect(getSpanColor(named('http.request.get'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS['http.']
    );
  });

  it('returns default color for unknown span names', () => {
    expect(getSpanColor(named('unknown.span'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS.default
    );
    expect(getSpanColor(named('custom.operation'), 'OK')).toBe(
      SEMANTIC_LAYER_COLORS.default
    );
  });

  it('handles empty span name', () => {
    expect(getSpanColor(named(''), 'OK')).toBe(SEMANTIC_LAYER_COLORS.default);
  });
});

describe('getSpanIcon', () => {
  it('picks the icon by span_type when the span has a specific one', () => {
    expect(getSpanIcon({ span_name: 'check', span_type: 'guardrail' })).toBe(
      ShieldIcon
    );
  });

  it('falls back to the span name for generic spans', () => {
    expect(
      getSpanIcon({ span_name: 'function.visit_prep_chat', span_type: 'span' })
    ).toBe(FunctionsIcon);
  });
});

import { findSpanPath, pickInitialSelection, treeTabIndex } from '../span-path';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

function span(span_id: string, children: SpanNode[] = []): SpanNode {
  return { span_id, children } as unknown as SpanNode;
}

const leaf = span('leaf');
const turn1 = span('turn-1', [span('t1-child')]);
const turn2 = span('turn-2', [span('t2-mid', [leaf])]);
const roots = [turn1, turn2];

describe('findSpanPath', () => {
  it('returns the root alone for a root span', () => {
    expect(findSpanPath(roots, 'turn-1')).toEqual([turn1]);
  });

  it('returns the root-to-span path for a nested span', () => {
    expect(findSpanPath(roots, 'leaf')?.map(s => s.span_id)).toEqual([
      'turn-2',
      't2-mid',
      'leaf',
    ]);
  });

  it('returns null for an unknown span', () => {
    expect(findSpanPath(roots, 'nope')).toBeNull();
  });
});

describe('treeTabIndex', () => {
  it('counts the Conversation tab when present', () => {
    expect(treeTabIndex(true)).toBe(1);
    expect(treeTabIndex(false)).toBe(0);
  });
});

describe('pickInitialSelection', () => {
  const trace = { root_spans: roots };

  it('selects the first root and keeps the tab by default', () => {
    expect(pickInitialSelection(trace, {})).toEqual({
      span: turn1,
      openTree: false,
    });
  });

  it('selects a found span and opens the Tree tab', () => {
    expect(pickInitialSelection(trace, { initialSpanId: 'leaf' })).toEqual({
      span: leaf,
      openTree: true,
    });
  });

  it('prefers the span over the turn index', () => {
    expect(
      pickInitialSelection(trace, {
        initialSpanId: 'leaf',
        initialTurnIndex: 0,
      }).span
    ).toBe(leaf);
  });

  it('falls back to the turn index when the span is missing', () => {
    expect(
      pickInitialSelection(trace, {
        initialSpanId: 'nope',
        initialTurnIndex: 1,
      })
    ).toEqual({ span: turn2, openTree: true });
  });

  it('falls back to the first root when the span is missing', () => {
    expect(pickInitialSelection(trace, { initialSpanId: 'nope' })).toEqual({
      span: turn1,
      openTree: false,
    });
  });

  it('clamps an out-of-range turn index', () => {
    expect(pickInitialSelection(trace, { initialTurnIndex: 9 }).span).toBe(
      turn2
    );
  });

  it('selects nothing for a trace without roots', () => {
    expect(
      pickInitialSelection({ root_spans: [] }, { initialSpanId: 'leaf' })
    ).toEqual({ span: null, openTree: false });
  });
});

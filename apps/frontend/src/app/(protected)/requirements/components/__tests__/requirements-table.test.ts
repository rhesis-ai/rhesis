import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import {
  completeness,
  orderByHierarchy,
  readRequirementsView,
  storeRequirementsView,
} from '../requirements-table';

const req = (id: string, parentId?: string) =>
  ({
    id,
    name: id,
    parent_id: parentId ?? null,
    metrics: [],
  }) as unknown as RequirementWithMetrics;

describe('orderByHierarchy', () => {
  it('puts children right after their parent, indented', () => {
    const rows = [req('a'), req('c1', 'p'), req('p'), req('c2', 'p')];
    expect(
      orderByHierarchy(rows).map(r => [r.requirement.id, r.depth])
    ).toEqual([
      ['a', 0],
      ['p', 0],
      ['c1', 1],
      ['c2', 1],
    ]);
  });

  it('keeps grandchildren under their parent', () => {
    const rows = [req('g', 'c'), req('c', 'p'), req('p')];
    expect(
      orderByHierarchy(rows).map(r => [r.requirement.id, r.depth])
    ).toEqual([
      ['p', 0],
      ['c', 1],
      ['g', 2],
    ]);
  });

  it('leaves a child top-level when its parent is on another page', () => {
    expect(orderByHierarchy([req('c', 'elsewhere')]).map(r => r.depth)).toEqual(
      [0]
    );
  });

  it('still shows every row when the data has a parent cycle', () => {
    const rows = [req('x', 'y'), req('y', 'x')];
    expect(orderByHierarchy(rows)).toHaveLength(2);
  });
});

describe('completeness', () => {
  it('marks each of the four checks', () => {
    const dots = completeness({
      description: 'Text',
      sources: [],
      examples_count: 2,
      metrics: [{}] as RequirementWithMetrics['metrics'],
    });
    expect(dots.map(d => [d.key, d.done])).toEqual([
      ['description', true],
      ['source', false],
      ['examples', true],
      ['metric', true],
    ]);
  });
});

describe('view preference', () => {
  afterEach(() => window.localStorage.clear());

  it('defaults to cards and remembers the table', () => {
    expect(readRequirementsView()).toBe('cards');
    storeRequirementsView('table');
    expect(readRequirementsView()).toBe('table');
  });

  it('falls back to cards when storage throws', () => {
    const spy = jest
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation(() => {
        throw new Error('blocked');
      });
    expect(readRequirementsView()).toBe('cards');
    spy.mockRestore();
  });
});

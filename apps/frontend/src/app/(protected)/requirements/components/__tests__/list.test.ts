import { emptyFilters, buildListFilter } from '@/utils/list';
import { requirementsList } from '../list';

const empty = emptyFilters(requirementsList);

describe('requirementsList filters', () => {
  it('contributes nothing when no filter is active, matching the old builder', () => {
    expect(buildListFilter(requirementsList, empty)).toBeUndefined();
  });

  it('ORs search across name/description plus linked metric and tag names, matching the old builder', () => {
    expect(buildListFilter(requirementsList, { ...empty, search: 'abc' })).toBe(
      "(contains(tolower(name),tolower('abc')) or contains(tolower(description),tolower('abc')) or " +
        "metrics/any(x: (contains(tolower(x/name),tolower('abc')) or contains(tolower(x/description),tolower('abc')))) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('abc'))))"
    );
  });

  it('maps has_metrics/no_metrics to metrics/any(), and anything else to no clause', () => {
    expect(
      buildListFilter(requirementsList, {
        ...empty,
        metricCount: 'has_metrics',
      })
    ).toBe('metrics/any()');
    expect(
      buildListFilter(requirementsList, {
        ...empty,
        metricCount: 'no_metrics',
      })
    ).toBe('not metrics/any()');
    expect(
      buildListFilter(requirementsList, {
        ...empty,
        metricCount: 'all',
      })
    ).toBeUndefined();
  });

  it('ORs tagNames and wraps them in any(), matching the old builder', () => {
    expect(
      buildListFilter(requirementsList, {
        ...empty,
        tagNames: ['red', 'blue'],
      })
    ).toBe(
      "_tags_relationship/any(x: (tolower(x/tag/name) eq tolower('red') or tolower(x/tag/name) eq tolower('blue')))"
    );
  });

  it('ANDs active filters together', () => {
    expect(
      buildListFilter(requirementsList, {
        ...empty,
        metricCount: 'has_metrics',
        tagNames: ['red'],
      })
    ).toBe(
      "metrics/any() and _tags_relationship/any(x: tolower(x/tag/name) eq tolower('red'))"
    );
  });

  it('ORs type and impact ids, dropping anything that is not a UUID', () => {
    const a = '11111111-1111-1111-1111-111111111111';
    const b = '22222222-2222-2222-2222-222222222222';
    expect(
      buildListFilter(requirementsList, {
        ...empty,
        typeIds: [a, "x' or 1 eq 1"],
      })
    ).toBe(`requirement_type_id eq ${a}`);
    expect(
      buildListFilter(requirementsList, { ...empty, impactIds: [a, b] })
    ).toBe(`(impact_id eq ${a} or impact_id eq ${b})`);
  });

  it('maps the hierarchy filter to parent_id clauses', () => {
    const parent = '33333333-3333-3333-3333-333333333333';
    expect(
      buildListFilter(requirementsList, { ...empty, hierarchy: 'top_level' })
    ).toBe('parent_id eq null');
    expect(
      buildListFilter(requirementsList, { ...empty, hierarchy: 'has_parent' })
    ).toBe('parent_id ne null');
    expect(
      buildListFilter(requirementsList, { ...empty, hierarchy: parent })
    ).toBe(`parent_id eq ${parent}`);
    expect(
      buildListFilter(requirementsList, { ...empty, hierarchy: 'all' })
    ).toBeUndefined();
  });
});

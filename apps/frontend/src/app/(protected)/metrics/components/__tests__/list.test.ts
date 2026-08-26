import { emptyFilters, buildListFilter, listParams } from '@/utils/list';
import {
  metricsList,
  METRICS_SELECT,
  OWASP_METRIC_FILTER_VALUE,
} from '../list';

const empty = emptyFilters(metricsList);

describe('metricsList filters', () => {
  it('contributes nothing when no filter is active, matching the old builder', () => {
    expect(buildListFilter(metricsList, empty)).toBeUndefined();
  });

  it('ORs search across name/description, matching the old builder', () => {
    expect(buildListFilter(metricsList, { ...empty, search: 'abc' })).toBe(
      "(contains(tolower(name),tolower('abc')) or contains(tolower(description),tolower('abc')))"
    );
  });

  it('maps the OWASP pseudo-backend value to a tag clause, everything else to backend_type', () => {
    expect(
      buildListFilter(metricsList, {
        ...empty,
        backend: ['Custom', OWASP_METRIC_FILTER_VALUE],
      })
    ).toBe(
      "(tolower(backend_type/type_value) eq 'Custom' or " +
        "_tags_relationship/any(x: tolower(x/tag/name) eq tolower('OWASP')))"
    );
  });

  it('ORs type/scoreType case-insensitively, matching the old builder', () => {
    expect(
      buildListFilter(metricsList, {
        ...empty,
        type: ['grading'],
        scoreType: ['numeric', 'categorical'],
      })
    ).toBe(
      "tolower(metric_type/type_value) eq tolower('grading') and " +
        "(tolower(score_type) eq tolower('numeric') or tolower(score_type) eq tolower('categorical'))"
    );
  });

  it('wraps requirement in any(), matching the old builder', () => {
    expect(
      buildListFilter(metricsList, { ...empty, requirement: 'Req A' })
    ).toBe("requirements/any(x: tolower(x/name) eq tolower('Req A'))");
  });

  it('leaves metricScope out of $filter entirely -- it is a dedicated query param', () => {
    expect(
      buildListFilter(metricsList, {
        ...empty,
        metricScope: ['Single-Turn'],
      })
    ).toBeUndefined();
  });
});

describe('metricsList extraParams', () => {
  it('always includes the trimmed $select', () => {
    const params = listParams(metricsList, {
      page: 1,
      pageSize: 25,
      sort: metricsList.defaultSort,
      filters: empty,
    });
    expect(params.$select).toBe(METRICS_SELECT);
    expect(params).not.toHaveProperty('metric_scope');
  });

  it('joins metricScope into a comma-separated query param, not $filter', () => {
    const params = listParams(metricsList, {
      page: 1,
      pageSize: 25,
      sort: metricsList.defaultSort,
      filters: { ...empty, metricScope: ['Single-Turn', 'Multi-Turn'] },
    });
    expect(params.metric_scope).toBe('Single-Turn,Multi-Turn');
    expect(params).not.toHaveProperty('$filter');
  });
});

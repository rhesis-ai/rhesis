import {
  filtersFromSearchParams,
  hasMetricUrlFilters,
  withMetricUrlState,
} from '../metric-url-state';
import type { FilterState } from '../MetricsDirectoryTab';

const empty: FilterState = {
  search: '',
  backend: [],
  type: [],
  scoreType: [],
  target: [],
  requirement: '',
};

const full: FilterState = {
  search: '',
  backend: ['custom', 'owasp'],
  type: ['custom-prompt'],
  scoreType: ['numeric'],
  target: ['turn', 'tool_call'],
  requirement: 'Safety & tone',
};

describe('metric URL state', () => {
  it('round-trips every filter', () => {
    const params = withMetricUrlState(new URLSearchParams(), full);
    expect(filtersFromSearchParams(params)).toEqual(full);
  });

  it('writes targets under the target param', () => {
    const params = withMetricUrlState(new URLSearchParams(), {
      ...empty,
      target: ['conversation'],
    });
    expect(params.toString()).toBe('target=conversation');
  });

  it('reads a quick filter link', () => {
    expect(
      filtersFromSearchParams(new URLSearchParams('backend=custom'))
    ).toEqual({ ...empty, backend: ['custom'] });
  });

  it('writes nothing for empty filters', () => {
    expect(withMetricUrlState(new URLSearchParams(), empty).toString()).toBe(
      ''
    );
  });

  it('leaves search text out of the URL', () => {
    const params = withMetricUrlState(new URLSearchParams(), {
      ...empty,
      search: 'tone',
    });
    expect(params.toString()).toBe('');
  });

  it('keeps params it does not own and clears stale filters', () => {
    const current = new URLSearchParams(
      'assignMode=true&backend=rhesis&score_type=numeric'
    );
    const next = withMetricUrlState(current, {
      ...empty,
      backend: ['custom'],
    });
    expect(next.get('assignMode')).toBe('true');
    expect(next.getAll('backend')).toEqual(['custom']);
    expect(next.has('score_type')).toBe(false);
  });

  it('drops values that do not parse', () => {
    const filters = filtersFromSearchParams(
      new URLSearchParams('score_type=bogus&target=Three-Turn&backend=')
    );
    expect(filters).toEqual(empty);
  });

  it('flags only filter params as narrowing the list', () => {
    expect(hasMetricUrlFilters(new URLSearchParams('assignMode=true'))).toBe(
      false
    );
    expect(hasMetricUrlFilters(new URLSearchParams('requirement=x'))).toBe(
      true
    );
  });

  it('does not flag empty or invalid filter values', () => {
    expect(
      hasMetricUrlFilters(
        new URLSearchParams('requirement=&target=Three-Turn&backend=')
      )
    ).toBe(false);
  });
});

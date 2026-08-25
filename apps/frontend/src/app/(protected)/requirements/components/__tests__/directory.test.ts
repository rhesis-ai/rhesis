import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { requirementsDirectory } from '../directory';

const empty = emptyFilters(requirementsDirectory);

describe('requirementsDirectory filters', () => {
  it('contributes nothing when no filter is active, matching the old builder', () => {
    expect(buildDirectoryFilter(requirementsDirectory, empty)).toBeUndefined();
  });

  it('ORs search across name/description plus linked metric and tag names, matching the old builder', () => {
    expect(
      buildDirectoryFilter(requirementsDirectory, { ...empty, search: 'abc' })
    ).toBe(
      "(contains(tolower(name),tolower('abc')) or contains(tolower(description),tolower('abc')) or " +
        "metrics/any(x: (contains(tolower(x/name),tolower('abc')) or contains(tolower(x/description),tolower('abc')))) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('abc'))))"
    );
  });

  it('maps has_metrics/no_metrics to metrics/any(), and anything else to no clause', () => {
    expect(
      buildDirectoryFilter(requirementsDirectory, {
        ...empty,
        metricCount: 'has_metrics',
      })
    ).toBe('metrics/any()');
    expect(
      buildDirectoryFilter(requirementsDirectory, {
        ...empty,
        metricCount: 'no_metrics',
      })
    ).toBe('not metrics/any()');
    expect(
      buildDirectoryFilter(requirementsDirectory, {
        ...empty,
        metricCount: 'all',
      })
    ).toBeUndefined();
  });

  it('ORs tagNames and wraps them in any(), matching the old builder', () => {
    expect(
      buildDirectoryFilter(requirementsDirectory, {
        ...empty,
        tagNames: ['red', 'blue'],
      })
    ).toBe(
      "_tags_relationship/any(x: (tolower(x/tag/name) eq tolower('red') or tolower(x/tag/name) eq tolower('blue')))"
    );
  });

  it('ANDs active filters together', () => {
    expect(
      buildDirectoryFilter(requirementsDirectory, {
        ...empty,
        metricCount: 'has_metrics',
        tagNames: ['red'],
      })
    ).toBe(
      "metrics/any() and _tags_relationship/any(x: tolower(x/tag/name) eq tolower('red'))"
    );
  });
});

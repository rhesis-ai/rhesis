import { emptyFilters, buildListFilter } from '@/utils/list';
import { experimentsList } from '../list';

const empty = emptyFilters(experimentsList);

describe('experimentsList filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildListFilter(experimentsList, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/description/visibility/project name, matching the old builder', () => {
    expect(buildListFilter(experimentsList, { ...empty, search: 'abc' })).toBe(
      "(contains(tolower(name),tolower('abc')) or " +
        "contains(tolower(description),tolower('abc')) or " +
        "contains(tolower(visibility),tolower('abc')) or " +
        "contains(tolower(project/name),tolower('abc')))"
    );
  });

  it('maps visibility to an exact case-insensitive match', () => {
    expect(
      buildListFilter(experimentsList, {
        ...empty,
        visibility: 'shared',
      })
    ).toBe("tolower(visibility) eq tolower('shared')");
  });
});

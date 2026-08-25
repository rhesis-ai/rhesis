import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { experimentsDirectory } from '../directory';

const empty = emptyFilters(experimentsDirectory);

describe('experimentsDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(experimentsDirectory, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/description/visibility/project name, matching the old builder', () => {
    expect(
      buildDirectoryFilter(experimentsDirectory, { ...empty, search: 'abc' })
    ).toBe(
      "(contains(tolower(name),tolower('abc')) or " +
        "contains(tolower(description),tolower('abc')) or " +
        "contains(tolower(visibility),tolower('abc')) or " +
        "contains(tolower(project/name),tolower('abc')))"
    );
  });

  it('maps visibility to an exact case-insensitive match', () => {
    expect(
      buildDirectoryFilter(experimentsDirectory, {
        ...empty,
        visibility: 'shared',
      })
    ).toBe("tolower(visibility) eq tolower('shared')");
  });
});

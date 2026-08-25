import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { testSetsDirectory } from '../directory';

const empty = emptyFilters(testSetsDirectory);

describe('testSetsDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(testSetsDirectory, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/creator/type plus a tags match, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testSetsDirectory, {
        ...empty,
        search: 'regression',
      })
    ).toBe(
      "(contains(tolower(name),tolower('regression')) or " +
        "contains(tolower(user/name),tolower('regression')) or " +
        "contains(tolower(test_set_type/type_value),tolower('regression')) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('regression'))))"
    );
  });

  it('maps testSetType to test_set_type/type_value, case-insensitively', () => {
    expect(
      buildDirectoryFilter(testSetsDirectory, {
        ...empty,
        testSetType: 'manual',
      })
    ).toBe("tolower(test_set_type/type_value) eq tolower('manual')");
  });

  it('matches status/creator with contains, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testSetsDirectory, { ...empty, status: 'Ready' })
    ).toBe("contains(tolower(status/name),tolower('Ready'))");
    expect(
      buildDirectoryFilter(testSetsDirectory, { ...empty, creator: 'alice' })
    ).toBe("contains(tolower(user/name),tolower('alice'))");
  });

  it('matches tag with a tags-relationship contains', () => {
    expect(
      buildDirectoryFilter(testSetsDirectory, { ...empty, tag: 'important' })
    ).toBe(
      "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('important')))"
    );
  });

  it('maps presence filters to the matching relationship, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testSetsDirectory, {
        ...empty,
        tagsPresence: 'with',
      })
    ).toBe('_tags_relationship/any()');
    expect(
      buildDirectoryFilter(testSetsDirectory, {
        ...empty,
        commentsPresence: 'without',
      })
    ).toBe('not comments/any()');
    expect(
      buildDirectoryFilter(testSetsDirectory, {
        ...empty,
        tasksPresence: 'with',
      })
    ).toBe('tasks/any()');
  });
});

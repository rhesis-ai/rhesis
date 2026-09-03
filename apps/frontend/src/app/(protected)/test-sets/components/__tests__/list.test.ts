import { emptyFilters, buildListFilter } from '@/utils/list';
import { testSetsList } from '../list';

const empty = emptyFilters(testSetsList);

describe('testSetsList filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildListFilter(testSetsList, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/creator/type plus a tags match, matching the old builder', () => {
    expect(
      buildListFilter(testSetsList, {
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
      buildListFilter(testSetsList, {
        ...empty,
        testSetType: 'manual',
      })
    ).toBe("tolower(test_set_type/type_value) eq tolower('manual')");
  });

  it('matches status/creator with contains, matching the old builder', () => {
    expect(buildListFilter(testSetsList, { ...empty, status: 'Ready' })).toBe(
      "contains(tolower(status/name),tolower('Ready'))"
    );
    expect(buildListFilter(testSetsList, { ...empty, creator: 'alice' })).toBe(
      "contains(tolower(user/name),tolower('alice'))"
    );
  });

  it('matches tag with a tags-relationship contains', () => {
    expect(buildListFilter(testSetsList, { ...empty, tag: 'important' })).toBe(
      "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('important')))"
    );
  });

  it('maps presence filters to the matching relationship, matching the old builder', () => {
    expect(
      buildListFilter(testSetsList, {
        ...empty,
        tagsPresence: 'with',
      })
    ).toBe('_tags_relationship/any()');
    expect(
      buildListFilter(testSetsList, {
        ...empty,
        commentsPresence: 'without',
      })
    ).toBe('not comments/any()');
    expect(
      buildListFilter(testSetsList, {
        ...empty,
        tasksPresence: 'with',
      })
    ).toBe('tasks/any()');
  });
});

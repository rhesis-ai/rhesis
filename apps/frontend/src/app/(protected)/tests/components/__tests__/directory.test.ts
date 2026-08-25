import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { testsDirectory } from '../directory';

const empty = emptyFilters(testsDirectory);

describe('testsDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(testsDirectory, empty)).toBeUndefined();
  });

  it('ORs the quick search across prompt/requirement/topic/category plus a tags match, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testsDirectory, { ...empty, search: 'abc' })
    ).toBe(
      "(contains(tolower(prompt/content),tolower('abc')) or " +
        "contains(tolower(requirement/name),tolower('abc')) or " +
        "contains(tolower(topic/name),tolower('abc')) or " +
        "contains(tolower(category/name),tolower('abc')) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('abc'))))"
    );
  });

  it('maps testType/requirement/category/topic to their columns, case-insensitively', () => {
    expect(
      buildDirectoryFilter(testsDirectory, {
        ...empty,
        testType: 'Single-Turn',
      })
    ).toBe("tolower(test_type/type_value) eq tolower('Single-Turn')");
    expect(
      buildDirectoryFilter(testsDirectory, { ...empty, requirement: 'Req A' })
    ).toBe("tolower(requirement/name) eq tolower('Req A')");
    expect(
      buildDirectoryFilter(testsDirectory, { ...empty, category: 'Bias' })
    ).toBe("tolower(category/name) eq tolower('Bias')");
    expect(
      buildDirectoryFilter(testsDirectory, { ...empty, topic: 'Safety' })
    ).toBe("tolower(topic/name) eq tolower('Safety')");
  });

  it('maps presence filters to the matching relationship, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testsDirectory, {
        ...empty,
        tagsPresence: 'with',
      })
    ).toBe('_tags_relationship/any()');
    expect(
      buildDirectoryFilter(testsDirectory, {
        ...empty,
        commentsPresence: 'without',
      })
    ).toBe('not comments/any()');
    expect(
      buildDirectoryFilter(testsDirectory, {
        ...empty,
        tasksPresence: 'with',
      })
    ).toBe('tasks/any()');
  });

  it('ANDs an extra clause in for the Insights failed-tests deep link', () => {
    expect(buildDirectoryFilter(testsDirectory, empty, ["id eq 'abc'"])).toBe(
      "id eq 'abc'"
    );
  });
});

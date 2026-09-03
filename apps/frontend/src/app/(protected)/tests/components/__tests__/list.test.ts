import { emptyFilters, buildListFilter } from '@/utils/list';
import { testsList } from '../list';

const empty = emptyFilters(testsList);

describe('testsList filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildListFilter(testsList, empty)).toBeUndefined();
  });

  it('ORs the quick search across prompt/requirement/topic/category plus a tags match, matching the old builder', () => {
    expect(buildListFilter(testsList, { ...empty, search: 'abc' })).toBe(
      "(contains(tolower(prompt/content),tolower('abc')) or " +
        "contains(tolower(requirement/name),tolower('abc')) or " +
        "contains(tolower(topic/name),tolower('abc')) or " +
        "contains(tolower(category/name),tolower('abc')) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('abc'))))"
    );
  });

  it('maps testType/requirement/category/topic to their columns, case-insensitively', () => {
    expect(
      buildListFilter(testsList, {
        ...empty,
        testType: 'Single-Turn',
      })
    ).toBe("tolower(test_type/type_value) eq tolower('Single-Turn')");
    expect(buildListFilter(testsList, { ...empty, requirement: 'Req A' })).toBe(
      "tolower(requirement/name) eq tolower('Req A')"
    );
    expect(buildListFilter(testsList, { ...empty, category: 'Bias' })).toBe(
      "tolower(category/name) eq tolower('Bias')"
    );
    expect(buildListFilter(testsList, { ...empty, topic: 'Safety' })).toBe(
      "tolower(topic/name) eq tolower('Safety')"
    );
  });

  it('maps presence filters to the matching relationship, matching the old builder', () => {
    expect(
      buildListFilter(testsList, {
        ...empty,
        tagsPresence: 'with',
      })
    ).toBe('_tags_relationship/any()');
    expect(
      buildListFilter(testsList, {
        ...empty,
        commentsPresence: 'without',
      })
    ).toBe('not comments/any()');
    expect(
      buildListFilter(testsList, {
        ...empty,
        tasksPresence: 'with',
      })
    ).toBe('tasks/any()');
  });

  it('ANDs an extra clause in for the Insights failed-tests deep link', () => {
    expect(buildListFilter(testsList, empty, ["id eq 'abc'"])).toBe(
      "id eq 'abc'"
    );
  });
});

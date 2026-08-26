import { emptyFilters, buildListFilter, listParams } from '@/utils/list';
import { testRunsList } from '../list';

const empty = emptyFilters(testRunsList);

describe('testRunsList filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildListFilter(testRunsList, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/test set/executor/status plus a tags match, matching the old builder', () => {
    expect(buildListFilter(testRunsList, { ...empty, search: 'nightly' })).toBe(
      "(contains(tolower(name),tolower('nightly')) or " +
        "contains(tolower(test_configuration/test_set/name),tolower('nightly')) or " +
        "contains(tolower(user/name),tolower('nightly')) or " +
        "contains(tolower(status/name),tolower('nightly')) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('nightly'))))"
    );
  });

  it('maps status to status/name, matching the old pill-tab filter', () => {
    expect(
      buildListFilter(testRunsList, { ...empty, status: 'Completed' })
    ).toBe("tolower(status/name) eq tolower('Completed')");
  });

  it('matches testSet/executor with contains, matching the old builder', () => {
    expect(
      buildListFilter(testRunsList, { ...empty, testSet: 'Nightly' })
    ).toBe(
      "contains(tolower(test_configuration/test_set/name),tolower('Nightly'))"
    );
    expect(buildListFilter(testRunsList, { ...empty, executor: 'Alice' })).toBe(
      "contains(tolower(user/name),tolower('Alice'))"
    );
  });

  it('matches tag with a tags-relationship contains', () => {
    expect(buildListFilter(testRunsList, { ...empty, tag: 'urgent' })).toBe(
      "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('urgent')))"
    );
  });

  it('maps presence filters to the matching relationship, matching the old builder', () => {
    expect(
      buildListFilter(testRunsList, {
        ...empty,
        tagsPresence: 'with',
      })
    ).toBe('_tags_relationship/any()');
    expect(
      buildListFilter(testRunsList, {
        ...empty,
        commentsPresence: 'without',
      })
    ).toBe('not comments/any()');
    expect(
      buildListFilter(testRunsList, {
        ...empty,
        tasksPresence: 'with',
      })
    ).toBe('tasks/any()');
  });

  it('leaves runKind/reviews out of $filter entirely -- they are dedicated query params', () => {
    expect(
      buildListFilter(testRunsList, {
        ...empty,
        runKind: 'tests',
        reviews: 'with',
      })
    ).toBeUndefined();
  });
});

describe('testRunsList extraParams', () => {
  it('maps runKind to has_experiment', () => {
    const params = listParams(testRunsList, {
      page: 1,
      pageSize: 50,
      sort: testRunsList.defaultSort,
      filters: { ...empty, runKind: 'tests' },
    });
    expect(params.has_experiment).toBe(false);

    const params2 = listParams(testRunsList, {
      page: 1,
      pageSize: 50,
      sort: testRunsList.defaultSort,
      filters: { ...empty, runKind: 'experiments' },
    });
    expect(params2.has_experiment).toBe(true);
  });

  it('maps reviews to has_reviews', () => {
    const params = listParams(testRunsList, {
      page: 1,
      pageSize: 50,
      sort: testRunsList.defaultSort,
      filters: { ...empty, reviews: 'with' },
    });
    expect(params.has_reviews).toBe(true);

    const params2 = listParams(testRunsList, {
      page: 1,
      pageSize: 50,
      sort: testRunsList.defaultSort,
      filters: { ...empty, reviews: 'without' },
    });
    expect(params2.has_reviews).toBe(false);
  });

  it('omits has_experiment/has_reviews entirely when unset', () => {
    const params = listParams(testRunsList, {
      page: 1,
      pageSize: 50,
      sort: testRunsList.defaultSort,
      filters: empty,
    });
    expect(params).not.toHaveProperty('has_experiment');
    expect(params).not.toHaveProperty('has_reviews');
  });
});

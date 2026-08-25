import {
  emptyFilters,
  buildDirectoryFilter,
  directoryListParams,
} from '@/utils/directory';
import { testRunsDirectory } from '../directory';

const empty = emptyFilters(testRunsDirectory);

describe('testRunsDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(testRunsDirectory, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/test set/executor/status plus a tags match, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testRunsDirectory, { ...empty, search: 'nightly' })
    ).toBe(
      "(contains(tolower(name),tolower('nightly')) or " +
        "contains(tolower(test_configuration/test_set/name),tolower('nightly')) or " +
        "contains(tolower(user/name),tolower('nightly')) or " +
        "contains(tolower(status/name),tolower('nightly')) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('nightly'))))"
    );
  });

  it('maps status to status/name, matching the old pill-tab filter', () => {
    expect(
      buildDirectoryFilter(testRunsDirectory, { ...empty, status: 'Completed' })
    ).toBe("tolower(status/name) eq tolower('Completed')");
  });

  it('matches testSet/executor with contains, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testRunsDirectory, { ...empty, testSet: 'Nightly' })
    ).toBe(
      "contains(tolower(test_configuration/test_set/name),tolower('Nightly'))"
    );
    expect(
      buildDirectoryFilter(testRunsDirectory, { ...empty, executor: 'Alice' })
    ).toBe("contains(tolower(user/name),tolower('Alice'))");
  });

  it('matches tag with a tags-relationship contains', () => {
    expect(
      buildDirectoryFilter(testRunsDirectory, { ...empty, tag: 'urgent' })
    ).toBe(
      "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('urgent')))"
    );
  });

  it('maps presence filters to the matching relationship, matching the old builder', () => {
    expect(
      buildDirectoryFilter(testRunsDirectory, {
        ...empty,
        tagsPresence: 'with',
      })
    ).toBe('_tags_relationship/any()');
    expect(
      buildDirectoryFilter(testRunsDirectory, {
        ...empty,
        commentsPresence: 'without',
      })
    ).toBe('not comments/any()');
    expect(
      buildDirectoryFilter(testRunsDirectory, {
        ...empty,
        tasksPresence: 'with',
      })
    ).toBe('tasks/any()');
  });

  it('leaves runKind/reviews out of $filter entirely -- they are dedicated query params', () => {
    expect(
      buildDirectoryFilter(testRunsDirectory, {
        ...empty,
        runKind: 'tests',
        reviews: 'with',
      })
    ).toBeUndefined();
  });
});

describe('testRunsDirectory extraParams', () => {
  it('maps runKind to has_experiment', () => {
    const params = directoryListParams(testRunsDirectory, {
      page: 1,
      pageSize: 50,
      sort: testRunsDirectory.defaultSort,
      filters: { ...empty, runKind: 'tests' },
    });
    expect(params.has_experiment).toBe(false);

    const params2 = directoryListParams(testRunsDirectory, {
      page: 1,
      pageSize: 50,
      sort: testRunsDirectory.defaultSort,
      filters: { ...empty, runKind: 'experiments' },
    });
    expect(params2.has_experiment).toBe(true);
  });

  it('maps reviews to has_reviews', () => {
    const params = directoryListParams(testRunsDirectory, {
      page: 1,
      pageSize: 50,
      sort: testRunsDirectory.defaultSort,
      filters: { ...empty, reviews: 'with' },
    });
    expect(params.has_reviews).toBe(true);

    const params2 = directoryListParams(testRunsDirectory, {
      page: 1,
      pageSize: 50,
      sort: testRunsDirectory.defaultSort,
      filters: { ...empty, reviews: 'without' },
    });
    expect(params2.has_reviews).toBe(false);
  });

  it('omits has_experiment/has_reviews entirely when unset', () => {
    const params = directoryListParams(testRunsDirectory, {
      page: 1,
      pageSize: 50,
      sort: testRunsDirectory.defaultSort,
      filters: empty,
    });
    expect(params).not.toHaveProperty('has_experiment');
    expect(params).not.toHaveProperty('has_reviews');
  });
});

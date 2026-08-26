import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { emptyFilters, listParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import { parseInsightsFailedTestsSearchParams } from '@/app/(protected)/insights/utils/insights-failed-tests';
import TestsPageClient from './components/TestsPageClient';
import { testsList } from './components/list';

interface TestsPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Server component: fetches the first page of tests before rendering so the
 * page arrives with content already in place -- no client-side spinner on
 * first load. See `prefetchList` for the permission-gating rationale.
 *
 * Exception: an Insights "failed tests" deep link resolves its test-id
 * filter client-side after first render, so the server can't build the
 * first page's `$filter` -- skip the prefetch and let the client fetch once
 * the filter resolves.
 */
export default async function TestsPage({ searchParams }: TestsPageProps) {
  const params = await searchParams;
  const insightsFilter = parseInsightsFailedTestsSearchParams({
    get: key => {
      const value = params[key];
      return (Array.isArray(value) ? value[0] : value) ?? null;
    },
  });

  if (insightsFilter) {
    return <TestsPageClient />;
  }

  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Test.READ,
    () =>
      testsList.list(
        factory,
        listParams(testsList, {
          page: 1,
          pageSize: testsList.defaultPageSize,
          sort: testsList.defaultSort,
          filters: emptyFilters(testsList),
        })
      )
  );

  return (
    <TestsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

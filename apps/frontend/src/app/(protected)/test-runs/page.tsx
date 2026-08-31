import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import TestRunsPageClient from './components/TestRunsPageClient';
import { testRunsList } from './components/list';

/**
 * Server component: fetches the first page of test runs before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function TestRunsPage() {
  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.TestRun.READ,
    () =>
      testRunsList.list(factory, firstPageParams(testRunsList))
  );

  return (
    <TestRunsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

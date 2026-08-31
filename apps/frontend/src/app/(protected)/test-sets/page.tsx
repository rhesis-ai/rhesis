import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import TestSetsPageClient from './components/TestSetsPageClient';
import { testSetsList } from './components/list';

/**
 * Server component: fetches the first page of test sets before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function TestSetsPage() {
  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.TestSet.READ,
    () =>
      testSetsList.list(factory, firstPageParams(testSetsList))
  );

  return (
    <TestSetsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

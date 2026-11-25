import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import ReportsPageClient from '../components/ReportsPageClient';
import { reportsList } from '../components/list';

/** Server component: prefetches the first page so the list arrives filled. */
export default async function ReportsPage() {
  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Report.READ,
    () => reportsList.list(factory, firstPageParams(reportsList))
  );

  return (
    <ReportsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

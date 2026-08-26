import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { emptyFilters, listParams } from '@/utils/list';
import JobsPageClient from './components/JobsPageClient';
import { jobsList } from './components/list';

/**
 * Server component: fetches the first page of jobs before rendering so the
 * page arrives with content already in place -- no client-side spinner on
 * first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function JobsPage() {
  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    jobsList.capability,
    () =>
      jobsList.list(
        factory,
        listParams(jobsList, {
          page: 1,
          pageSize: jobsList.defaultPageSize,
          sort: jobsList.defaultSort,
          filters: emptyFilters(jobsList),
        })
      )
  );

  return (
    <JobsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

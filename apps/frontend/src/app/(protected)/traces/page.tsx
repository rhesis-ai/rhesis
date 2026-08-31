export const dynamic = 'force-dynamic';

import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { prefetchList } from '@/utils/server-prefetch';
import { emptyFilters, listParams } from '@/utils/list';
import TracesClientWrapper from './components/TracesClientWrapper';
import { tracesList } from './components/list';
import { requireSession } from '@/utils/require-session';

interface TracesPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Server component for the Traces page. Prefetches page 1 scoped to the
 * active project (read from the same `rh_active_project_id` cookie the client
 * uses), honouring a `?project_id=` override the same way the drawer filter
 * does, so an empty project renders its empty state on first paint instead
 * of a grid skeleton. Falls back to the client fetch when no project is
 * scoped yet.
 */
export default async function TracesPage({ searchParams }: TracesPageProps) {
  const session = await requireSession();

  const [params, scopedProjectId] = await Promise.all([
    searchParams,
    getServerActiveProjectId(),
  ]);
  const urlProjectId =
    typeof params.project_id === 'string' ? params.project_id : '';

  let initialData;
  let initialTotalCount = 0;
  if (scopedProjectId) {
    const factory = await createServerApiFactory();
    const descriptor = tracesList(scopedProjectId, factory);
    ({ initialData, initialTotalCount } = await prefetchList(
      descriptor.capability,
      () =>
        descriptor.list(
          factory,
          listParams(descriptor, {
            page: 1,
            pageSize: descriptor.defaultPageSize,
            sort: descriptor.defaultSort,
            filters: { ...emptyFilters(descriptor), projectId: urlProjectId },
          })
        )
    ));
  }

  return (
    <TracesClientWrapper
      currentUserId={session.user?.id || ''}
      currentUserName={session.user?.name || ''}
      currentUserPicture={session.user?.picture || undefined}
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

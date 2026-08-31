import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import TasksPageClient from './components/TasksPageClient';
import { tasksList } from './components/list';

/**
 * Server component: fetches the first page of tasks before rendering so the
 * page arrives with content already in place -- no client-side spinner on
 * first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function TasksPage() {
  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Task.READ,
    () =>
      tasksList.list(factory, firstPageParams(tasksList))
  );

  return (
    <TasksPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

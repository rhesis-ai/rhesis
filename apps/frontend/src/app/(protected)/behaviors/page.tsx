import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import BehaviorsClient from './components/BehaviorsClient';
import { DEFAULT_BEHAVIORS_PAGE_SIZE } from './components/behaviors-constants';
import type { UUID } from 'crypto';

/**
 * Server component: fetches the first page of behaviors before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. Permission gating (`useCan`) stays client-side since it
 * depends on the `PermissionsContext` seeded by `(protected)/layout.tsx`,
 * which resolves synchronously on first render.
 */
export default async function BehaviorsPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const organizationId = session.user?.organization_id as UUID;
  const userId = (session.user?.id as UUID | undefined) ?? undefined;

  const client = (await createServerApiFactory()).getBehaviorClient();

  let initialData;
  let initialTotalCount = 0;
  try {
    const response = await client.getBehaviorsPage({
      skip: 0,
      limit: DEFAULT_BEHAVIORS_PAGE_SIZE,
      sort_by: 'name',
      sort_order: 'asc',
    });
    initialData = response.data;
    initialTotalCount = response.pagination.totalCount;
  } catch {
    // Fall back to client-side fetching on the initial mount.
    initialData = undefined;
  }

  const serializedInitialData = initialData
    ? JSON.parse(JSON.stringify(initialData))
    : undefined;

  return (
    <BehaviorsClient
      organizationId={organizationId}
      userId={userId}
      initialData={serializedInitialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

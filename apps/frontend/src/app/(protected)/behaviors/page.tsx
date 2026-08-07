import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import BehaviorsClient from './components/BehaviorsClient';
import { DEFAULT_BEHAVIORS_PAGE_SIZE } from './components/behaviors-constants';
import type { UUID } from 'crypto';

/**
 * Server component: fetches the first page of behaviors before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function BehaviorsPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const organizationId = session.user?.organization_id as UUID;
  const userId = (session.user?.id as UUID | undefined) ?? undefined;
  const client = (await createServerApiFactory()).getBehaviorClient();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Behavior.READ,
    () =>
      client.getBehaviorsPage({
        skip: 0,
        limit: DEFAULT_BEHAVIORS_PAGE_SIZE,
        sort_by: 'name',
        sort_order: 'asc',
      })
  );

  return (
    <BehaviorsClient
      organizationId={organizationId}
      userId={userId}
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

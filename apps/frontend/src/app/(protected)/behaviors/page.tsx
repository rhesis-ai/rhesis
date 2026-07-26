import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { hasServerCapability } from '@/utils/server-permissions';
import { Capability } from '@/constants/capabilities';
import BehaviorsClient from './components/BehaviorsClient';
import { DEFAULT_BEHAVIORS_PAGE_SIZE } from './components/behaviors-constants';
import type { UUID } from 'crypto';

/**
 * Server component: fetches the first page of behaviors before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load.
 *
 * The `Behavior.READ` check runs here, server-side, before the prefetch: an
 * unauthorized user's client-side `useCan` gate in `BehaviorsClient` renders
 * an AccessDenied screen, but that alone doesn't stop real data from being
 * serialized into the page's initial payload -- this check does.
 */
export default async function BehaviorsPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const organizationId = session.user?.organization_id as UUID;
  const userId = (session.user?.id as UUID | undefined) ?? undefined;
  const canRead = await hasServerCapability(Capability.Behavior.READ);

  const client = (await createServerApiFactory()).getBehaviorClient();

  let initialData;
  let initialTotalCount = 0;
  if (canRead) {
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

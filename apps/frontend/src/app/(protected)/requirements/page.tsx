import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import RequirementsClient from './components/RequirementsClient';
import { requirementsList } from './components/list';
import type { UUID } from 'crypto';

/**
 * Server component: fetches the first page of requirements before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function RequirementsPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const organizationId = session.user?.organization_id as UUID;
  const userId = (session.user?.id as UUID | undefined) ?? undefined;
  const client = (await createServerApiFactory()).getRequirementClient();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Requirement.READ,
    () =>
      client.getRequirementsPage(firstPageParams(requirementsList))
  );

  return (
    <RequirementsClient
      organizationId={organizationId}
      userId={userId}
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

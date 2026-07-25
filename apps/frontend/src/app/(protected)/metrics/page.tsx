import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';
import { METRICS_SELECT, DEFAULT_METRICS_PAGE_SIZE } from './components/metrics-constants';

/**
 * Server component: fetches the first page of metrics before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. Permission gating (`useCan`) stays client-side since it
 * depends on the `PermissionsContext` seeded by `(protected)/layout.tsx`,
 * which resolves synchronously on first render.
 */
export default async function MetricsPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const organizationId = session.user?.organization_id as UUID;

  const client = (await createServerApiFactory()).getMetricsClient();

  let initialData;
  let initialTotalCount = 0;
  try {
    const response = await client.getMetrics({
      skip: 0,
      limit: DEFAULT_METRICS_PAGE_SIZE,
      sort_by: 'created_at',
      sort_order: 'desc',
      $select: METRICS_SELECT,
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
    <MetricsClientComponent
      organizationId={organizationId}
      initialData={serializedInitialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

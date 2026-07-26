import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { hasServerCapability } from '@/utils/server-permissions';
import { Capability } from '@/constants/capabilities';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';
import {
  METRICS_SELECT,
  DEFAULT_METRICS_PAGE_SIZE,
} from './components/metrics-constants';

/**
 * Server component: fetches the first page of metrics before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load.
 *
 * The `Metric.READ` check runs here, server-side, before the prefetch: it's
 * not just a render gate, it decides whether metrics data is fetched and
 * embedded in the response at all. `MetricsClientComponent` still resolves
 * `useCan` client-side too, so a user whose permissions change mid-session
 * gets a consistent client-side AccessDenied without a full reload.
 */
export default async function MetricsPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const organizationId = session.user?.organization_id as UUID;
  const canRead = await hasServerCapability(Capability.Metric.READ);

  const client = (await createServerApiFactory()).getMetricsClient();

  let initialData;
  let initialTotalCount = 0;
  if (canRead) {
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

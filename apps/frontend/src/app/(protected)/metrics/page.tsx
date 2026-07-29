import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';
import {
  METRICS_SELECT,
  DEFAULT_METRICS_PAGE_SIZE,
  METRICS_READ_CAPABILITY,
} from './components/metrics-constants';

/**
 * Server component: fetches the first page of metrics before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function MetricsPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const organizationId = session.user?.organization_id as UUID;
  const client = (await createServerApiFactory()).getMetricsClient();

  const { initialData, initialTotalCount } = await prefetchList(
    METRICS_READ_CAPABILITY,
    () =>
      client.getMetrics({
        skip: 0,
        limit: DEFAULT_METRICS_PAGE_SIZE,
        sort_by: 'created_at',
        sort_order: 'desc',
        $select: METRICS_SELECT,
      })
  );

  return (
    <MetricsClientComponent
      organizationId={organizationId}
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

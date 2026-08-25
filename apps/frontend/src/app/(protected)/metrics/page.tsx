import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { emptyFilters, directoryListParams } from '@/utils/directory';
import { Capability } from '@/constants/capabilities';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';
import { metricsDirectory } from './components/directory';

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
    Capability.Metric.READ,
    () =>
      client.getMetrics(
        directoryListParams(metricsDirectory, {
          page: 1,
          pageSize: metricsDirectory.defaultPageSize,
          sort: metricsDirectory.defaultSort,
          filters: emptyFilters(metricsDirectory),
        })
      )
  );

  return (
    <MetricsClientComponent
      organizationId={organizationId}
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import { requireSession } from '@/utils/require-session';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';
import { metricsList } from './components/list';
import { hasMetricUrlFilters } from './components/metric-url-state';

interface MetricsPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Server component: fetches the first page of metrics before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function MetricsPage({ searchParams }: MetricsPageProps) {
  const session = await requireSession();

  const organizationId = session.user?.organization_id as UUID;

  const urlParams = new URLSearchParams();
  Object.entries(await searchParams).forEach(([key, value]) =>
    [value ?? []].flat().forEach(v => urlParams.append(key, v))
  );

  // An unfiltered first page wouldn't match a filtered URL; let the client fetch.
  let initialData;
  let initialTotalCount = 0;
  if (!hasMetricUrlFilters(urlParams)) {
    const client = (await createServerApiFactory()).getMetricsClient();
    ({ initialData, initialTotalCount } = await prefetchList(
      Capability.Metric.READ,
      () => client.getMetrics(firstPageParams(metricsList))
    ));
  }

  return (
    <MetricsClientComponent
      organizationId={organizationId}
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

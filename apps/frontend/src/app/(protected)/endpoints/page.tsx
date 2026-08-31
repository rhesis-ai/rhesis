import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import EndpointsPageClient from './components/EndpointsPageClient';
import { endpointsList } from './components/list';

/**
 * Server component: fetches the first page of endpoints before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function EndpointsPage() {
  const client = (await createServerApiFactory()).getEndpointsClient();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Endpoint.READ,
    () => client.getEndpoints(firstPageParams(endpointsList))
  );

  return (
    <EndpointsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

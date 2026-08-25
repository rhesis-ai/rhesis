import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { emptyFilters, directoryListParams } from '@/utils/directory';
import { Capability } from '@/constants/capabilities';
import EndpointsPageClient from './components/EndpointsPageClient';
import { endpointsDirectory } from './components/directory';

/**
 * Server component: fetches the first page of endpoints before rendering so
 * the page arrives with content already in place -- no client-side spinner
 * on first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function EndpointsPage() {
  const client = (await createServerApiFactory()).getEndpointsClient();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Endpoint.READ,
    () =>
      client.getEndpoints(
        directoryListParams(endpointsDirectory, {
          page: 1,
          pageSize: endpointsDirectory.defaultPageSize,
          sort: endpointsDirectory.defaultSort,
          filters: emptyFilters(endpointsDirectory),
        })
      )
  );

  return (
    <EndpointsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}

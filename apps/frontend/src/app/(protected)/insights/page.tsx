import * as React from 'react';
import { cookies } from 'next/headers';
import {
  HydrationBoundary,
  QueryClient,
  dehydrate,
} from '@tanstack/react-query';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { hasServerCapability } from '@/utils/server-permissions';
import { Capability } from '@/constants/capabilities';
import { endpointKeys } from '@/constants/query-keys';
import { INSIGHTS_ENDPOINT_COOKIE } from '@/utils/insights-endpoint';
import InsightsPage from './components/InsightsPage';
import { DEFAULT_INSIGHTS_FILTERS, normalizeInsightsFilters } from './types';
import {
  fetchRequirementInsights,
  pickEndpointId,
  resolveInsightsQueryTestRunIds,
  type RequirementInsightsResult,
} from './utils/requirement-insights-utils';

// Must match the params `InsightsPage` passes to `useEndpoints`, or the
// hydrated cache entry lands under a different key and goes unused.
const ENDPOINT_LIST_PARAMS = {
  limit: 100,
  sort_by: 'name',
  sort_order: 'asc',
} as const;

/**
 * Server component: resolves the endpoint the client would pick (same cookie
 * and project rules as `resolveEndpointId`) and fetches its default-filter
 * insights, so the first paint shows numbers instead of a spinner. Endpoints
 * are hydrated into the react-query cache under `useEndpoints`' key. Fails
 * open to "no initial data" so the client falls back to its own fetches.
 */
export default async function InsightsRoutePage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('No session token available');
  }

  const queryClient = new QueryClient();
  let initialEndpointId: string | undefined;
  let initialInsights: RequirementInsightsResult | undefined;

  if (await hasServerCapability(Capability.TestResult.READ)) {
    try {
      const [factory, projectId, cookieStore] = await Promise.all([
        createServerApiFactory(),
        getServerActiveProjectId(),
        cookies(),
      ]);

      const endpoints = JSON.parse(
        JSON.stringify(
          (
            await factory
              .getEndpointsClient()
              .getEndpoints(ENDPOINT_LIST_PARAMS)
          ).data ?? []
        )
      );
      queryClient.setQueryData(
        endpointKeys.list(
          '',
          0,
          ENDPOINT_LIST_PARAMS.limit,
          ENDPOINT_LIST_PARAMS.sort_by,
          ENDPOINT_LIST_PARAMS.sort_order
        ),
        endpoints
      );

      const endpointId = pickEndpointId(
        endpoints,
        projectId,
        cookieStore.get(INSIGHTS_ENDPOINT_COOKIE)?.value ?? null
      );

      if (endpointId) {
        const filters = normalizeInsightsFilters({
          ...DEFAULT_INSIGHTS_FILTERS,
          endpointId,
        });
        const testRunIds = await resolveInsightsQueryTestRunIds(
          filters,
          factory
        );
        const insights = await fetchRequirementInsights(
          filters,
          testRunIds,
          factory
        );
        initialEndpointId = endpointId;
        initialInsights = JSON.parse(JSON.stringify(insights));
      }
    } catch {
      // Fall back to the client's own fetches.
      initialEndpointId = undefined;
      initialInsights = undefined;
    }
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <InsightsPage
        initialEndpointId={initialEndpointId}
        initialInsights={initialInsights}
      />
    </HydrationBoundary>
  );
}

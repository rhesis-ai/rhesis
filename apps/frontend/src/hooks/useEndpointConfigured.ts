'use client';

import { useQuery } from '@tanstack/react-query';
import { endpointKeys } from '@/constants/query-keys';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { type EndpointSetupStatus } from '@/utils/api-client/interfaces/endpoint';
import { useUserScope } from '@/hooks/useIsAuthenticated';

/**
 * Whether the active project has an endpoint of its own (seeded example ones,
 * like the example project's or the local mock chatbot, don't count).
 * `undefined` until known, or when no project is active.
 */
export function useEndpointConfigured(enabled = true): boolean | undefined {
  const { activeProject } = useActiveProject();
  const userScope = useUserScope();
  const projectId = activeProject?.id ?? '';

  const { data } = useQuery<EndpointSetupStatus>({
    queryKey: endpointKeys.setupStatus(userScope, projectId),
    queryFn: () => new ApiClientFactory().getEndpointsClient().getSetupStatus(),
    enabled: enabled && !!userScope && !!projectId,
  });

  return data?.configured ?? undefined;
}

'use client';

import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { modelKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ModelDetail } from '@/utils/api-client/interfaces/model';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

/**
 * Cached model list from GET /models, sorted by name.
 *
 * Shared across every `ModelSelector` instance so mounting several at once
 * (e.g. Evaluation + Execution model in `RunDrawer`) fetches once instead
 * of once per instance.
 */
export function useModels(sessionToken: string, enabled = true) {
  const { status } = useSession();
  return useQuery<ModelDetail[]>({
    queryKey: modelKeys.list('', 0, 100, 'name', 'asc'),
    queryFn: async () => {
      const response = await new ApiClientFactory(sessionToken)
        .getModelsClient()
        .getModels({ sort_by: 'name', sort_order: 'asc', skip: 0, limit: 100 });
      return response.data || [];
    },
    enabled: enabled && isAuthenticated(status),
    staleTime: 5 * 60_000,
  });
}

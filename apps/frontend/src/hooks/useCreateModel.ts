'use client';

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { modelKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Model, ModelCreate } from '@/utils/api-client/interfaces/model';

/** Creates a model connection; shared by the Models page and the "Connect a model" step. */
export function useCreateModel(): (modelData: ModelCreate) => Promise<Model> {
  const { status } = useSession();
  const queryClient = useQueryClient();

  return useCallback(
    async (modelData: ModelCreate) => {
      if (!isAuthenticated(status)) throw new Error('No session token');
      const model = await new ApiClientFactory()
        .getModelsClient()
        .createModel(modelData);
      queryClient.invalidateQueries({ queryKey: modelKeys.all() });
      return model;
    },
    [status, queryClient]
  );
}

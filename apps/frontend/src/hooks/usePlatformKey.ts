'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { modelKeys, platformKeyKeys } from '@/constants/query-keys';
import {
  getRhesisPlatformKeyStatus,
  setRhesisPlatformKey,
  clearRhesisPlatformKey,
} from '@/utils/api-client/platform-client';
import type { PlatformKeyStatus } from '@/utils/api-client/interfaces/platform';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { useRhesisKeyEnabled } from '@/contexts/FeaturesContext';

/**
 * Status of, and mutations for, the deployment-wide Rhesis platform API key.
 *
 * Only fetches when ENABLE_RHESIS_KEY is set (the backend endpoints 404
 * otherwise). On a successful set/clear the models query is invalidated so
 * any grid greying that depends on model availability re-resolves.
 */
export function usePlatformKey(enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  const rhesisKeyEnabled = useRhesisKeyEnabled();
  const queryClient = useQueryClient();

  const query = useQuery<PlatformKeyStatus>({
    queryKey: platformKeyKeys.all(),
    queryFn: getRhesisPlatformKeyStatus,
    enabled: enabled && isAuthenticated && rhesisKeyEnabled,
    staleTime: 60_000,
  });

  const invalidateModels = () => {
    queryClient.invalidateQueries({ queryKey: modelKeys.all() });
  };

  const setKey = useMutation({
    mutationFn: (key: string) => setRhesisPlatformKey(key),
    onSuccess: status => {
      queryClient.setQueryData(platformKeyKeys.all(), status);
      invalidateModels();
    },
  });

  const clearKey = useMutation({
    mutationFn: () => clearRhesisPlatformKey(),
    onSuccess: status => {
      queryClient.setQueryData(platformKeyKeys.all(), status);
      invalidateModels();
    },
  });

  return { query, setKey, clearKey, rhesisKeyEnabled };
}

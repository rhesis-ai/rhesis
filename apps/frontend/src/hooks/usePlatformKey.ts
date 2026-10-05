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
import {
  useRefreshFeatures,
  useRhesisKeyEnabled,
} from '@/contexts/FeaturesContext';

/**
 * Status of, and mutations for, the deployment-wide Rhesis platform API key.
 *
 * Only fetches when ENABLE_RHESIS_KEY is set (the backend endpoints 404
 * otherwise). On a successful set/clear the models query is invalidated so
 * any grid greying that depends on model availability re-resolves, and
 * `GET /features` is refetched because the key decides model readiness.
 */
export function usePlatformKey(enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  const rhesisKeyEnabled = useRhesisKeyEnabled();
  const queryClient = useQueryClient();
  const refreshFeatures = useRefreshFeatures();

  const query = useQuery<PlatformKeyStatus>({
    queryKey: platformKeyKeys.all(),
    queryFn: getRhesisPlatformKeyStatus,
    enabled: enabled && isAuthenticated && rhesisKeyEnabled,
    staleTime: 60_000,
  });

  const invalidateModels = () => {
    queryClient.invalidateQueries({ queryKey: modelKeys.all() });
    void refreshFeatures();
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

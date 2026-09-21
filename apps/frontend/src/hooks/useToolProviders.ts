'use client';

import { useQuery } from '@tanstack/react-query';
import { toolProviderKeys } from '@/constants/query-keys';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { ToolProvider } from '@/utils/api-client/interfaces/tool-provider';

/**
 * Cached longer than the usual lookup: the provider set is compiled into the
 * backend, so it changes on release rather than on user action.
 */
const STALE_TIME = 30 * 60_000;

/**
 * Providers this deployment supports, from `GET /tools/providers`.
 *
 * The server is the only place that knows which auth methods an install can
 * actually offer, so the grid and the connection form read this rather than a
 * frontend constant.
 */
export function useToolProviders(enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<ToolProvider[]>({
    queryKey: toolProviderKeys.all(),
    queryFn: () => new ApiClientFactory().getToolsClient().getToolProviders(),
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

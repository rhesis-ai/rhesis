'use client';

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { usageKeys } from '@/constants/query-keys';
import { useUserScope } from '@/hooks/useIsAuthenticated';

/**
 * Returns a callback that drops the cached `GET /usage` response.
 *
 * Call it after creating or deleting a **stock** resource (a project, an
 * endpoint, a member/seat). `UsageContext` caches for five minutes, so
 * without this a user who deletes a project because a quota notice told
 * them to stays blocked for up to five minutes, having done exactly what
 * was asked.
 *
 * Flow resources (test runs, generation, spans, tokens) deliberately stay on
 * `staleTime`: a stale flow count only ever drifts up, so the preflight errs
 * open and the server-side 402 catches it.
 *
 * `usageKeys.all(userScope)` is the `['usage', userScope]` prefix, so this
 * also invalidates the history and past-period queries beneath it.
 */
export function useInvalidateUsage(): () => void {
  const queryClient = useQueryClient();
  const userScope = useUserScope();

  return useCallback(() => {
    if (!userScope) return;
    queryClient.invalidateQueries({ queryKey: usageKeys.all(userScope) });
  }, [queryClient, userScope]);
}

'use client';

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { endpointKeys } from '@/constants/query-keys';
import { useInvalidateUsage } from '@/hooks/useInvalidateUsage';
import { createEndpoint } from '@/actions/endpoints';

/**
 * Wraps the `createEndpoint` server action so every caller invalidates the
 * endpoints list and the usage cache the same way. Not a `useMutation`
 * because the server action never throws on a business failure — it
 * returns `{ success: false, error }` instead — so invalidation only fires
 * once here, on `result.success`, rather than at every call site.
 *
 * Kept out of `useEndpoints.ts`: that file's other hooks are imported all
 * over the app, and `createEndpoint` (a server action) pulls in `src/auth.ts`
 * and the NextAuth server bundle. Bundling them together would drag that
 * into every one of those unrelated consumers.
 */
export function useCreateEndpoint() {
  const queryClient = useQueryClient();
  const invalidateUsage = useInvalidateUsage();
  return useCallback(
    async (data: Parameters<typeof createEndpoint>[0]) => {
      const result = await createEndpoint(data);
      if (result.success) {
        queryClient.invalidateQueries({ queryKey: endpointKeys.all() });
        // Endpoints are a stock resource: creating one consumes quota, and
        // the endpoints gate reads the cached count.
        invalidateUsage();
      }
      return result;
    },
    [queryClient, invalidateUsage]
  );
}

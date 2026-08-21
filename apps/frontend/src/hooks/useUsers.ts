'use client';

import { useCallback } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UserCreate } from '@/utils/api-client/interfaces/user';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { useInvalidateUsage } from '@/hooks/useInvalidateUsage';

/**
 * Wraps `UsersClient.createUser` so every caller invalidates the usage
 * cache the same way. Seats are a stock resource: creating a user consumes
 * one, and the invite gate reads the cached count.
 */
export function useCreateUser() {
  const isAuthenticated = useIsAuthenticated();
  const invalidateUsage = useInvalidateUsage();
  return useCallback(
    async (data: UserCreate) => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }
      const user = await new ApiClientFactory()
        .getUsersClient()
        .createUser(data);
      invalidateUsage();
      return user;
    },
    [isAuthenticated, invalidateUsage]
  );
}

/** Removing a member frees a seat. */
export function useDeleteUser() {
  const isAuthenticated = useIsAuthenticated();
  const invalidateUsage = useInvalidateUsage();
  return useCallback(
    async (id: string) => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }
      await new ApiClientFactory().getUsersClient().deleteUser(id);
      invalidateUsage();
    },
    [isAuthenticated, invalidateUsage]
  );
}

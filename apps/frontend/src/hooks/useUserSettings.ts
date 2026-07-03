'use client';

import { QueryClient, useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { userSettingsKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UserSettings } from '@/utils/api-client/interfaces/user';

/**
 * Cached current-user settings from GET /users/settings.
 *
 * Scoped by user id (falling back to the session token) so the cache never
 * bleeds across login/logout or user switches, matching the pattern used by
 * `featureKeys`/`permissionKeys`.
 */
export function useUserSettings() {
  const { data: session, status } = useSession();
  const sessionToken =
    status === 'authenticated' ? session?.session_token : undefined;
  const userScope = session?.user?.id ?? sessionToken ?? '';

  return useQuery<UserSettings>({
    queryKey: userSettingsKeys.all(userScope),
    queryFn: () =>
      new ApiClientFactory(sessionToken!).getUsersClient().getUserSettings(),
    enabled: !!sessionToken,
    staleTime: 5 * 60_000,
  });
}

/**
 * Imperative counterpart for call sites outside a render path (e.g. inside
 * an async callback). Joins the same cache/dedup as `useUserSettings`.
 */
export function fetchUserSettings(
  queryClient: QueryClient,
  sessionToken: string,
  userScope: string
) {
  return queryClient.fetchQuery({
    queryKey: userSettingsKeys.all(userScope),
    queryFn: () =>
      new ApiClientFactory(sessionToken).getUsersClient().getUserSettings(),
    staleTime: 5 * 60_000,
  });
}

/** Write-through the cache after a settings mutation, e.g. `updateUserSettings`. */
export function writeUserSettingsCache(
  queryClient: QueryClient,
  userScope: string,
  settings: UserSettings
) {
  queryClient.setQueryData(userSettingsKeys.all(userScope), settings);
}

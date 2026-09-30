'use client';

import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { onboardingStatusKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { OnboardingStatus } from '@/utils/api-client/interfaces/user';
import { isAuthenticated, useUserScope } from '@/hooks/useIsAuthenticated';

/**
 * Onboarding steps computed from real data by GET /users/onboarding-status, so
 * work done through the SDK or any page counts without a tour marking it.
 * Re-read on mount and when the window regains focus.
 *
 * Pass `enabled = false` once the checklist is dismissed or complete; there is
 * nothing left for it to show.
 */
export function useOnboardingStatus(enabled: boolean) {
  const { data: session, status } = useSession();
  const userScope = useUserScope();

  return useQuery<OnboardingStatus>({
    queryKey: onboardingStatusKeys.all(userScope),
    queryFn: () =>
      new ApiClientFactory().getUsersClient().getOnboardingStatus(),
    // The route needs an organization; a user mid-onboarding has none yet.
    enabled:
      enabled &&
      isAuthenticated(status) &&
      !!userScope &&
      !!session?.user?.organization_id,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });
}

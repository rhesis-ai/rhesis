'use client';

import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { onboardingStatusKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { OnboardingStatus } from '@/utils/api-client/interfaces/user';
import { isAuthenticated, useUserScope } from '@/hooks/useIsAuthenticated';
import { OnboardingProgress } from '@/types/onboarding';
import {
  applyServerStatus,
  isOnboardingComplete,
} from '@/utils/onboarding-service';

/**
 * Onboarding steps computed from real data by GET /users/onboarding-status, so
 * work done through the SDK or any page counts without a tour marking it.
 * Re-read on mount and window focus until local progress plus the server's
 * answer completes the checklist, or it is dismissed.
 */
export function useOnboardingStatus(progress: OnboardingProgress) {
  const { data: session, status } = useSession();
  const userScope = useUserScope();
  const done = (data: OnboardingStatus | undefined) =>
    isOnboardingComplete(applyServerStatus(progress, data));
  const refetch = (query: { state: { data?: OnboardingStatus } }) =>
    done(query.state.data) ? false : ('always' as const);

  return useQuery<OnboardingStatus>({
    queryKey: onboardingStatusKeys.all(userScope),
    queryFn: () =>
      new ApiClientFactory().getUsersClient().getOnboardingStatus(),
    // The route needs an organization; a user mid-onboarding has none yet.
    enabled:
      !progress.dismissed &&
      !isOnboardingComplete(progress) &&
      isAuthenticated(status) &&
      !!userScope &&
      !!session?.user?.organization_id,
    refetchOnMount: refetch,
    refetchOnWindowFocus: refetch,
  });
}

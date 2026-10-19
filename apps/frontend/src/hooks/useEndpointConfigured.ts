'use client';

import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { onboardingStatusKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { type OnboardingStatus } from '@/utils/api-client/interfaces/user';
import { isAuthenticated, useUserScope } from '@/hooks/useIsAuthenticated';

/**
 * Whether the organization has an endpoint of its own (the seeded example
 * doesn't count). `undefined` until known. Shares the onboarding-status cache.
 */
export function useEndpointConfigured(enabled = true): boolean | undefined {
  const { data: session, status } = useSession();
  const userScope = useUserScope();

  const { data } = useQuery<OnboardingStatus>({
    queryKey: onboardingStatusKeys.all(userScope),
    queryFn: () =>
      new ApiClientFactory().getUsersClient().getOnboardingStatus(),
    enabled:
      enabled &&
      isAuthenticated(status) &&
      !!userScope &&
      !!session?.user?.organization_id,
  });

  return data?.endpoint_setup;
}

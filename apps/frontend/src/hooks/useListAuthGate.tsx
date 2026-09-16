'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { useCanWithStatus } from '@/components/common/Can';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

interface UseListAuthGateOptions {
  /** A single capability, or two combined with OR (e.g. Annotations' TestResult.READ / Telemetry.READ). */
  capability: string | readonly [string, string];
  resource: string;
  title: string;
}

type ListAuthGateResult =
  { ready: true } | { ready: false; node: React.ReactNode };

/**
 * Shared client-side render gate for list pages: session loading -> perms
 * loading -> AccessDenied -> no-session, in that order, identical across every
 * page. This is the CLIENT-side check -- it always re-verifies, independent of
 * whatever `fetchListPage` decided server-side about whether to embed data
 * (see that function's docstring for why both layers matter).
 *
 * Capped at two capabilities (OR'd) because `useCanWithStatus` is a hook and
 * can't be called a variable number of times per render -- today only
 * Annotations needs two; extend this if a third page ever needs more.
 */
export function useListAuthGate({
  capability,
  resource,
  title,
}: UseListAuthGateOptions): ListAuthGateResult {
  const { status } = useSession();
  const [primary, secondary] = Array.isArray(capability)
    ? capability
    : [capability, undefined];

  const a = useCanWithStatus(primary);
  const b = useCanWithStatus(secondary ?? primary);

  const canRead = secondary ? a.allowed || b.allowed : a.allowed;
  const permsLoading = secondary ? a.loading || b.loading : a.loading;

  if (isSessionLoading(status)) {
    return {
      ready: false,
      node: (
        <PageLayout title={title} breadcrumbs={[]}>
          <Box sx={{ p: 3 }}>
            <Typography>Loading...</Typography>
          </Box>
        </PageLayout>
      ),
    };
  }

  if (permsLoading) {
    return { ready: false, node: <PageLoadingState /> };
  }

  if (!canRead) {
    return { ready: false, node: <AccessDenied resource={resource} /> };
  }

  if (!isAuthenticated(status)) {
    return {
      ready: false,
      node: (
        <PageLayout title={title} breadcrumbs={[]}>
          <Box sx={{ p: 3 }}>
            <Typography color="error">No session token available</Typography>
          </Box>
        </PageLayout>
      ),
    };
  }

  return { ready: true };
}

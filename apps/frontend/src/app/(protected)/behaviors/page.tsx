'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import BehaviorsClient from './components/BehaviorsClient';
import type { UUID } from 'crypto';

export default function BehaviorsPage() {
  const { data: session, status } = useSession();

  // Use memoized values to prevent unnecessary re-renders from session object recreation
  const sessionToken = React.useMemo(
    () => session?.session_token,
    [session?.session_token]
  );
  const organizationId = React.useMemo(
    () => session?.user?.organization_id as UUID,
    [session?.user?.organization_id]
  );

  // Handle loading state
  if (status === 'loading') {
    return (
      <PageLayout title="Behaviors" breadcrumbs={[]}>
        <Box
          sx={{
            p: 3,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: theme => theme.spacing(25),
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={24} />
            <Typography>Loading behaviors...</Typography>
          </Box>
        </Box>
      </PageLayout>
    );
  }

  // Handle no session state
  if (!sessionToken) {
    return (
      <PageLayout title="Behaviors" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">
            Authentication required. Please log in.
          </Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Behaviors" breadcrumbs={[]}>
      <BehaviorsClient
        sessionToken={sessionToken}
        organizationId={organizationId}
      />
    </PageLayout>
  );
}

'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { useSession } from 'next-auth/react';
import { PageContainer } from '@toolpad/core/PageContainer';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';

export default function MetricsPage() {
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
      <PageContainer title="Metrics" breadcrumbs={[]}>
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
            <Typography>Loading metrics...</Typography>
          </Box>
        </Box>
      </PageContainer>
    );
  }

  // Handle no session state
  if (!sessionToken) {
    return (
      <PageContainer title="Metrics" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">
            Authentication required. Please log in.
          </Typography>
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Metrics" breadcrumbs={[]}>
      <MetricsClientComponent
        sessionToken={sessionToken}
        organizationId={organizationId}
      />
    </PageContainer>
  );
}

'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { PageContainer } from '@toolpad/core/PageContainer';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TracesClient from './components/TracesClient';

/**
 * Traces page - view and analyze OpenTelemetry traces
 *
 * Client component that handles authentication and passes
 * session token to TracesClient component.
 */
export default function TracesPage() {
  const { data: session, status } = useSession();

  // Handle loading state
  if (status === 'loading') {
    return (
      <PageContainer
        title="Traces"
        breadcrumbs={[{ title: 'Traces', path: '/traces' }]}
      >
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageContainer>
    );
  }

  // Handle no session state
  if (!session?.session_token) {
    return (
      <PageContainer
        title="Traces"
        breadcrumbs={[{ title: 'Traces', path: '/traces' }]}
      >
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Traces"
      breadcrumbs={[{ title: 'Traces', path: '/traces' }]}
    >
      <TracesClient sessionToken={session.session_token} />
    </PageContainer>
  );
}

'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { useSession } from 'next-auth/react';
import BehaviorsClient from './components/BehaviorsClient';
import PageHeader from '@/components/layout/PageHeader';
import type { UUID } from 'crypto';

export default function BehaviorsPage() {
  const { data: session, status } = useSession();

  const sessionToken = React.useMemo(
    () => session?.session_token,
    [session?.session_token]
  );
  const organizationId = React.useMemo(
    () => session?.user?.organization_id as UUID,
    [session?.user?.organization_id]
  );

  if (status === 'loading') {
    return (
      <>
        <PageHeader
          title="Behaviors"
          description="Behaviors are atomic expectations for your application, measured through one or more metrics to determine if requirements are met."
        />
        <Box
          sx={{
            px: 4,
            pb: 4,
            pt: 3,
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
      </>
    );
  }

  if (!sessionToken) {
    return (
      <>
        <PageHeader
          title="Behaviors"
          description="Behaviors are atomic expectations for your application, measured through one or more metrics to determine if requirements are met."
        />
        <Box sx={{ px: 4, pb: 4, pt: 3 }}>
          <Typography color="error">
            Authentication required. Please log in.
          </Typography>
        </Box>
      </>
    );
  }

  return (
    <BehaviorsClient
      sessionToken={sessionToken}
      organizationId={organizationId}
    />
  );
}

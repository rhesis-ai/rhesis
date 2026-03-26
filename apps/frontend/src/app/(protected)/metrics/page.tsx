'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { useSession } from 'next-auth/react';
import MetricsClientComponent from './components/MetricsClient';
import PageHeader from '@/components/layout/PageHeader';
import type { UUID } from 'crypto';

export default function MetricsPage() {
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
          title="Metrics"
          description="Metrics are quantifiable measurements that evaluate behaviors and determine if requirements are met."
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
            <Typography>Loading metrics...</Typography>
          </Box>
        </Box>
      </>
    );
  }

  if (!sessionToken) {
    return (
      <>
        <PageHeader
          title="Metrics"
          description="Metrics are quantifiable measurements that evaluate behaviors and determine if requirements are met."
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
    <MetricsClientComponent
      sessionToken={sessionToken}
      organizationId={organizationId}
    />
  );
}

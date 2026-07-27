'use client';

import { Box, CircularProgress, Typography } from '@mui/material';
import { useSession } from 'next-auth/react';
import TestGenerationFlow from './components/TestGenerationFlow';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

export default function GenerateTestsPage() {
  const { status } = useSession();

  if (isSessionLoading(status)) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress sx={{ mb: 2 }} />
        <Typography variant="body1">Loading...</Typography>
      </Box>
    );
  }

  if (!isAuthenticated(status)) {
    throw new Error('No session token available');
  }

  return <TestGenerationFlow />;
}

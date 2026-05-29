'use client';

import { Box, CircularProgress, Typography } from '@mui/material';
import { useSession } from 'next-auth/react';
import TestGenerationFlow from './components/TestGenerationFlow';

export default function GenerateTestsPage() {
  const { data: session, status } = useSession();

  if (status === 'loading') {
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

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return <TestGenerationFlow sessionToken={session.session_token} />;
}

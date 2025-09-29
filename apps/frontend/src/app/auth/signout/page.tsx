'use client';

import { useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Box, Typography, CircularProgress } from '@mui/material';
import { handleClientSignOut } from '@/utils/client-auth';

export default function SignOut() {
  const searchParams = useSearchParams();

  useEffect(() => {
    console.log(
      '[ERROR] [DEBUG] SignOut page loaded, calling handleClientSignOut'
    );
    handleClientSignOut();
  }, []);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 2,
      }}
    >
      <CircularProgress />
      <Typography variant="body1">Signing out...</Typography>
    </Box>
  );
}

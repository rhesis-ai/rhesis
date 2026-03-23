'use client';

import { useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Box, Typography, CircularProgress } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import { handleClientSignOut } from '@/utils/client-auth';
import BackgroundDecoration from '@/components/auth/BackgroundDecoration';
import { lightTheme } from '@/styles/theme';

export default function SignOut() {
  const _searchParams = useSearchParams();

  useEffect(() => {
    handleClientSignOut();
  }, []);

  return (
    <ThemeProvider theme={lightTheme}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          gap: 2,
          bgcolor: 'background.default',
          position: 'relative',
        }}
      >
        <BackgroundDecoration />
        <Box
          sx={{
            position: 'relative',
            zIndex: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <CircularProgress />
          <Typography variant="body1">Signing out...</Typography>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

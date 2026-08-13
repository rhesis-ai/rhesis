'use client';

import { useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { Box, Typography, CircularProgress } from '@mui/material';
import { ThemeProvider, createTheme, useTheme } from '@mui/material/styles';
import { handleClientSignOut } from '@/utils/client-auth';
import BackgroundDecoration from '@/components/auth/BackgroundDecoration';
import { getDesignTokens } from '@/styles/theme';
import { scaledVh } from '@/styles/viewport-scaling';

export default function SignOut() {
  const _searchParams = useSearchParams();
  // This page pins light mode, so it can't use the ambient theme directly — but
  // it still has to honour a deployment's brand colour, which the spinner below
  // picks up from `palette.primary`. Rebuild the light theme with the brand
  // colour read off the ambient one instead of the static `lightTheme` export.
  const { brandColor, brandSecondaryColor } = useTheme().palette;
  const theme = useMemo(
    () =>
      createTheme(
        getDesignTokens('light', {
          primary: brandColor,
          secondary: brandSecondaryColor,
        })
      ),
    [brandColor, brandSecondaryColor]
  );

  useEffect(() => {
    // The backend logout call goes through the /api/backend proxy, which
    // injects the access token server-side from the httpOnly cookie — no
    // token is available (or needed) in browser JS.
    handleClientSignOut();
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: scaledVh(),
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

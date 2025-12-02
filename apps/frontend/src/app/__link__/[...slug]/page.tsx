'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Box, CircularProgress } from '@mui/material';

/**
 * This is a catch-all route for handling external link navigation.
 * When a user clicks an external link in the navigation, they are temporarily
 * routed here so the NavigationProvider can intercept and open the link
 * in a new tab, then navigate back.
 */
export default function LinkRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    // If we end up on this page, something went wrong with the interception
    // Navigate back to the previous page after a short delay
    const timeout = setTimeout(() => {
      router.back();
    }, 500);

    return () => clearTimeout(timeout);
  }, [router]);

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
      }}
    >
      <CircularProgress />
    </Box>
  );
}

'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { Box, CircularProgress } from '@mui/material';

// Dynamically import TestRunMainView with SSR disabled to prevent hydration mismatches
const TestRunMainView = dynamic(() => import('./TestRunMainView'), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '400px',
      }}
    >
      <CircularProgress />
    </Box>
  ),
});

function TestRunMainViewWrapper(props: React.ComponentProps<typeof TestRunMainView>) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '400px',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return <TestRunMainView {...props} />;
}

export default TestRunMainViewWrapper;

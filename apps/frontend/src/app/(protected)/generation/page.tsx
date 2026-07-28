'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Box, CircularProgress } from '@mui/material';
import { scaledVh } from '@/styles/viewport-scaling';

export default function GenerationRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/tests?openGeneration=true');
  }, [router]);

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: scaledVh(),
      }}
    >
      <CircularProgress />
    </Box>
  );
}

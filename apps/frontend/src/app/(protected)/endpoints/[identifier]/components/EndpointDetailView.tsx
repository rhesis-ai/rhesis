'use client';

import { Suspense } from 'react';
import { Box, CircularProgress } from '@mui/material';
import EndpointSummaryCard from './EndpointSummaryCard';
import EndpointDetailTabs from './EndpointDetailTabs';

function TabsFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
      <CircularProgress size={24} />
    </Box>
  );
}

export default function EndpointDetailView() {
  return (
    <>
      <EndpointSummaryCard />
      <Suspense fallback={<TabsFallback />}>
        <EndpointDetailTabs />
      </Suspense>
    </>
  );
}

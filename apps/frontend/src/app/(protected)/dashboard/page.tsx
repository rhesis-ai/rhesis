'use client';

import * as React from 'react';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import DashboardKPIs from './components/DashboardKPIs';
import TestRunPerformance from './components/TestRunPerformance';
import ActivityTimeline from './components/ActivityTimeline';
import { useSession } from 'next-auth/react';
import { PageContainer } from '@toolpad/core/PageContainer';

export default function DashboardPage() {
  const { data: session } = useSession();
  const [loadingStates, setLoadingStates] = React.useState({
    kpis: true,
    testRuns: true,
    activities: true,
  });

  const allLoaded =
    !loadingStates.kpis && !loadingStates.testRuns && !loadingStates.activities;

  const handleComponentLoad = React.useCallback(
    (component: 'kpis' | 'testRuns' | 'activities') => {
      setLoadingStates(prev => ({ ...prev, [component]: false }));
    },
    []
  );

  return (
    <PageContainer>
      {!allLoaded && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '60vh',
          }}
        >
          <CircularProgress size={48} />
        </Box>
      )}

      <Box sx={{ display: allLoaded ? 'block' : 'none' }}>
        {/* Hero KPI Section */}
        <DashboardKPIs
          sessionToken={session?.session_token || ''}
          onLoadComplete={() => handleComponentLoad('kpis')}
        />

        {/* Main Content Grid - 2x3 Layout (each takes half the width) */}
        <Grid container spacing={3}>
          {/* Recent Test Runs - 3x2 (6 columns = 50% width) */}
          <Grid item xs={12} md={6}>
            <TestRunPerformance
              sessionToken={session?.session_token || ''}
              onLoadComplete={() => handleComponentLoad('testRuns')}
            />
          </Grid>

          {/* Recent Activity Timeline - 1x3 (6 columns = 50% width) */}
          <Grid item xs={12} md={6}>
            <ActivityTimeline
              sessionToken={session?.session_token || ''}
              onLoadComplete={() => handleComponentLoad('activities')}
            />
          </Grid>
        </Grid>
      </Box>
    </PageContainer>
  );
}

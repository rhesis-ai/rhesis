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
import { useOnboarding } from '@/contexts/OnboardingContext';

export default function DashboardPage() {
  const { data: session } = useSession();
  const { forceSyncToDatabase } = useOnboarding();
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

  // Trigger immediate sync to database when dashboard loads
  React.useEffect(() => {
    if (session?.session_token) {
      forceSyncToDatabase();
    }
  }, [session?.session_token, forceSyncToDatabase]);

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

        {/* Main Content Grid - 2 Column Layout */}
        <Grid container spacing={3}>
          {/* Recent Test Runs - Left Column (4 test runs) */}
          <Grid size={{ xs: 12, md: 6 }}>
            <TestRunPerformance
              sessionToken={session?.session_token || ''}
              onLoadComplete={() => handleComponentLoad('testRuns')}
              limit={4}
            />
          </Grid>

          {/* Recent Activity Timeline - Right Column */}
          <Grid size={{ xs: 12, md: 6 }}>
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

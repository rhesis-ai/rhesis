'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid2';
import Paper from '@mui/material/Paper';
import DashboardCharts from './components/DashboardCharts';
import LatestTestRunsGrid from './components/LatestTestRunsGrid';
import RecentTestsGrid from './components/RecentTestsGrid';
import RecentTestSetsGrid from './components/RecentTestSetsGrid';
import RecentActivitiesGrid from './components/RecentActivitiesGrid';
import { useSession } from 'next-auth/react';
import {
  ScienceIcon,
  HorizontalSplitIcon,
  PlayArrowIcon,
} from '@/components/icons';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useOnboarding } from '@/contexts/OnboardingContext';

export default function DashboardPage() {
  const { data: session } = useSession();
  const { forceSyncToDatabase } = useOnboarding();

  // Trigger immediate sync to database when dashboard loads
  React.useEffect(() => {
    if (session?.session_token) {
      forceSyncToDatabase();
    }
  }, [session?.session_token, forceSyncToDatabase]);

  return (
    <PageContainer>
      {/* Charts Section */}
      <DashboardCharts />

      {/* DataGrids Section - 2x2 Grid */}

      <Grid container spacing={3} sx={{ mt: 2 }}>
        {/* Newest Tests - Top Left */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <ScienceIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Newest Tests
            </Typography>
            <RecentTestsGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>

        {/* Updated Tests - Top Right */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <ScienceIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Updated Tests
            </Typography>
            <RecentActivitiesGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>

        {/* Newest Test Sets - Bottom Left */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <HorizontalSplitIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Newest Test Sets
            </Typography>
            <RecentTestSetsGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>

        {/* Recent Test Runs - Bottom Right */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <PlayArrowIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Recent Test Runs
            </Typography>
            <LatestTestRunsGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>
      </Grid>
    </PageContainer>
  );
}

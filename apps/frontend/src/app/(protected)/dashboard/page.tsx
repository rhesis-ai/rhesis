'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import DashboardCharts from './components/DashboardCharts';
import LatestTestRunsGrid from './components/LatestTestRunsGrid';
import RecentTestsGrid from './components/RecentTestsGrid';
import RecentTestSetsGrid from './components/RecentTestSetsGrid';
import RecentActivitiesGrid from './components/RecentActivitiesGrid';
import OnboardingDashboardCard from '@/components/onboarding/OnboardingDashboardCard';
import { useSession } from 'next-auth/react';
import { useOnboarding } from '@/contexts/OnboardingContext';
import {
  ScienceIcon,
  HorizontalSplitIcon,
  PlayArrowIcon,
} from '@/components/icons';
import { PageContainer } from '@toolpad/core/PageContainer';

export default function DashboardPage() {
  const { data: session } = useSession();
  const [mounted, setMounted] = React.useState(false);
  const { progress, isComplete } = useOnboarding();

  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Check if onboarding should be shown
  const showOnboarding = mounted && !progress.dismissed && !isComplete;

  return (
    <PageContainer>
      {/* Charts Section */}
      <DashboardCharts />

      {/* DataGrids Section - Conditional 2x2 Grid */}

      <Grid container spacing={3} sx={{ mt: 2 }}>
        {/* Onboarding Card - Top Left (only when onboarding active) */}
        {showOnboarding && (
          <Grid item xs={12} md={6}>
            <OnboardingDashboardCard />
          </Grid>
        )}

        {/* Newest Tests - Top Right (or Top Left if no onboarding) */}
        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <ScienceIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Newest Tests
            </Typography>
            <RecentTestsGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>

        {/* Updated Tests - Top Right (only when onboarding dismissed) */}
        {!showOnboarding && (
          <Grid item xs={12} md={6}>
            <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
              <Typography variant="h6" sx={{ mb: 2 }}>
                <ScienceIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                Updated Tests
              </Typography>
              <RecentActivitiesGrid
                sessionToken={session?.session_token || ''}
              />
            </Paper>
          </Grid>
        )}

        {/* Newest Test Sets - Bottom Left */}
        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <HorizontalSplitIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Newest Test Sets
            </Typography>
            <RecentTestSetsGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>

        {/* Recent Test Runs - Bottom Right */}
        <Grid item xs={12} md={6}>
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

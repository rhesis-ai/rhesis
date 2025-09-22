'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import DashboardCharts from './components/DashboardCharts';
import LatestTestRunsGrid from './components/LatestTestRunsGrid';
import RecentTestsGrid from './components/RecentTestsGrid';
import RecentTestSetsGrid from './components/RecentTestSetsGrid';
import RecentActivitiesGrid from './components/RecentActivitiesGrid';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { UUID } from 'crypto';
import { ScienceIcon, HorizontalSplitIcon, PlayArrowIcon } from '@/components/icons';
import { PageContainer } from '@toolpad/core/PageContainer';

// Extended User interface with organization_id
interface ExtendedUser {
  id?: string;
  name?: string | null;
  email?: string | null;
  is_superuser?: boolean;
  organization_id?: UUID;
}

interface SessionUser {
  id: string;
  name?: string | null;
  email?: string | null;
  image?: string | null;
  organization_id?: string | null;
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const router = useRouter();
  
  // Check if user has organization_id
  useEffect(() => {
    const user = session?.user as ExtendedUser | undefined;

    // Removed organization_id check - now handled by middleware
  }, [session, router]);

  return (    
    <PageContainer>

      {/* Charts Section */}
      <DashboardCharts />

      {/* DataGrids Section */}  

      <Grid container spacing={3} sx={{ mt: 2 }}>
        {/* First row of DataGrids */}

        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <ScienceIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Newest Tests
            </Typography>
            <RecentTestsGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <ScienceIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Updated Tests
            </Typography>
            <RecentActivitiesGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>

        {/* Second row of DataGrids */}
        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              <HorizontalSplitIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Newest Test Sets
            </Typography>
            <RecentTestSetsGrid sessionToken={session?.session_token || ''} />
          </Paper>
        </Grid>
        
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

'use client';

import * as React from 'react';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import DashboardCharts from './components/DashboardCharts';
import DashboardKPIs from './components/DashboardKPIs';
import TestRunPerformance from './components/TestRunPerformance';
import ActivityTimeline from './components/ActivityTimeline';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { UUID } from 'crypto';
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
      {/* Hero KPI Section */}
      <DashboardKPIs sessionToken={session?.session_token || ''} />

      {/* Main Content Grid - Rows 2-3 */}
      <Grid container spacing={3}>
        {/* Left Column: 2x2 Grid (Behavior, Category, Test Runs) */}
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            {/* Top Row: Behavior and Category Distribution side by side */}
            <Box>
              <Grid container spacing={3}>
                <DashboardCharts />
              </Grid>
            </Box>

            {/* Bottom Row: Recent Test Runs spanning full width */}
            <TestRunPerformance sessionToken={session?.session_token || ''} />
          </Stack>
        </Grid>

        {/* Right Column: Recent Activity Timeline spanning full height */}
        <Grid item xs={12} md={4}>
          <ActivityTimeline sessionToken={session?.session_token || ''} />
        </Grid>
      </Grid>
    </PageContainer>
  );
}

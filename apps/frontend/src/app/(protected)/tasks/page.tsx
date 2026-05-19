'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import TasksGrid from './components/TasksGrid';
import TasksCharts from './components/TasksCharts';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export default function TasksPage() {
  const { data: session, status } = useSession();
  const [refreshKey, setRefreshKey] = React.useState(0);

  // Set document title
  useDocumentTitle('Tasks');

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  // Handle loading state
  if (status === 'loading') {
    return (
      <PageLayout title="Tasks" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  // Handle no session state
  if (!session?.session_token) {
    return (
      <PageLayout title="Tasks" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Tasks" breadcrumbs={[]}>
      {/* Charts Section */}
      <TasksCharts
        sessionToken={session.session_token}
        key={`charts-${refreshKey}`}
      />

      {/* Tasks Grid Section */}
      <Paper sx={{ p: 3 }}>
        <TasksGrid
          sessionToken={session.session_token}
          onRefresh={handleRefresh}
        />
      </Paper>
    </PageLayout>
  );
}

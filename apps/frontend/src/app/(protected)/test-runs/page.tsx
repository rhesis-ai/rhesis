'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { useSession } from 'next-auth/react';
import { PageContainer } from '@toolpad/core/PageContainer';
import TestRunsGrid from './components/TestRunsGrid';
import TestRunCharts from './components/TestRunCharts';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export default function TestRunsPage() {
  const { data: session, status } = useSession();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [totalCount, setTotalCount] = React.useState(0);

  // Set document title
  useDocumentTitle('Test Runs');

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleTotalCountChange = React.useCallback((count: number) => {
    setTotalCount(count);
  }, []);

  // Handle loading state
  if (status === 'loading') {
    return (
      <PageContainer
        title="Test Runs"
        breadcrumbs={[{ title: 'Test Runs', path: '/test-runs' }]}
      >
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageContainer>
    );
  }

  // Handle no session state
  if (!session?.session_token) {
    return (
      <PageContainer
        title="Test Runs"
        breadcrumbs={[{ title: 'Test Runs', path: '/test-runs' }]}
      >
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Test Runs"
      breadcrumbs={[{ title: 'Test Runs', path: '/test-runs' }]}
    >
      {/* Charts Section */}
      <TestRunCharts
        sessionToken={session.session_token}
        totalCount={totalCount}
        key={`charts-${refreshKey}`}
      />

      {/* Table Section */}
      <Paper sx={{ width: '100%', mb: 2, mt: 2 }}>
        <Box sx={{ p: 2 }}>
          <TestRunsGrid
            sessionToken={session.session_token}
            onRefresh={handleRefresh}
            onTotalCountChange={handleTotalCountChange}
            key={`grid-${refreshKey}`}
          />
        </Box>
      </Paper>
    </PageContainer>
  );
}

'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Toolbar } from '@/components/layout/Toolbar';
import TestRunsGrid from './components/TestRunsGrid';
import TestRunCharts from './components/TestRunCharts';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export default function TestRunsPage() {
  const { data: session, status } = useSession();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [searchQuery, setSearchQuery] = React.useState('');

  // Set document title
  useDocumentTitle('Test Runs');

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  // Handle loading state
  if (status === 'loading') {
    return (
      <PageLayout title="Test Runs" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  // Handle no session state
  if (!session?.session_token) {
    return (
      <PageLayout title="Test Runs" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Test Runs" breadcrumbs={[]}>
      {/* Charts Section */}
      <TestRunCharts
        sessionToken={session.session_token}
        key={`charts-${refreshKey}`}
      />

      {/* Table Section */}
      <Paper sx={{ width: '100%', mb: 2, mt: 2 }}>
        <Toolbar
          searchProps={{
            value: searchQuery,
            onChange: setSearchQuery,
            placeholder: 'Search test runs…',
          }}
        />
        <Box sx={{ p: 2 }}>
          <TestRunsGrid
            sessionToken={session.session_token}
            onRefresh={handleRefresh}
            key={`grid-${refreshKey}`}
          />
        </Box>
      </Paper>
    </PageLayout>
  );
}

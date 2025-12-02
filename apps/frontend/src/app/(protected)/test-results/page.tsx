import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { auth } from '@/auth';
import { PageContainer } from '@toolpad/core/PageContainer';
import TestResultsDashboard from './components/TestResultsDashboard';

export default async function TestResultsPage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    return (
      <PageContainer
        title="Test Results"
        breadcrumbs={[{ title: 'Test Results', path: '/test-results' }]}
      >
        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" color="text.secondary">
            Track and analyze test performance over time. Filter by time range,
            test set, or search for specific test runs.
          </Typography>
        </Box>
        <TestResultsDashboard sessionToken={session.session_token} />
      </PageContainer>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <PageContainer title="Test Results">
        <Paper elevation={2} sx={{ p: 3 }}>
          <Typography color="error" variant="h6" gutterBottom>
            Error Loading Test Results
          </Typography>
          <Typography color="text.secondary">{errorMessage}</Typography>
        </Paper>
      </PageContainer>
    );
  }
}

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { auth } from '@/auth';
import { PageLayout } from '@/components/layout/PageLayout';
import InsightsPage from './components/InsightsPage';

export default async function InsightsRoutePage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    return (
      <PageLayout title="Insights" breadcrumbs={[]}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" color="text.secondary">
            View pass rates by behavior, metric, and topic for your selected
            endpoint. Filter by time range or switch endpoints to compare
            performance.
          </Typography>
        </Box>
        <InsightsPage sessionToken={session.session_token} />
      </PageLayout>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <PageLayout title="Insights" breadcrumbs={[]}>
        <Paper elevation={2} sx={{ p: 3 }}>
          <Typography color="error" variant="h6" gutterBottom>
            Error Loading Insights
          </Typography>
          <Typography color="text.secondary">{errorMessage}</Typography>
        </Paper>
      </PageLayout>
    );
  }
}

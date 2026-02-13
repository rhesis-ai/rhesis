import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';
import AdaptiveTestingGrid from './components/AdaptiveTestingGrid';

export default async function AdaptiveTestingPage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(session.session_token);
    const adaptiveTestingClient = clientFactory.getAdaptiveTestingClient();

    // Fetch adaptive test sets using the dedicated endpoint
    const testSets = await adaptiveTestingClient.getAdaptiveTestSets();

    return (
      <PageContainer title="Adaptive Testing" breadcrumbs={[]}>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body1" color="text.secondary">
            Test sets configured for adaptive testing
          </Typography>
        </Box>

        <Paper sx={{ width: '100%', mb: 2 }}>
          <Box sx={{ p: 2 }}>
            <AdaptiveTestingGrid
              testSets={testSets}
              loading={false}
              sessionToken={session.session_token}
            />
          </Box>
        </Paper>
      </PageContainer>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Error loading adaptive testing: {errorMessage}
        </Typography>
      </Box>
    );
  }
}

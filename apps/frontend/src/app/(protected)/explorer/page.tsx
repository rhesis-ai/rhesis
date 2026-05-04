import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';
import ExplorerGrid from './components/ExplorerGrid';

export default async function ExplorerPage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(session.session_token);
    const explorerClient = clientFactory.getExplorerClient();

    // Fetch adaptive test sets using the dedicated endpoint
    const testSets = await explorerClient.getAdaptiveTestSets();

    return (
      <PageContainer title="Test explorer" breadcrumbs={[]}>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body1" color="text.secondary">
            Explorer sessions
          </Typography>
        </Box>

        <Paper sx={{ width: '100%', mb: 2 }}>
          <Box sx={{ p: 2 }}>
            <ExplorerGrid
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
          Error loading test explorer: {errorMessage}
        </Typography>
      </Box>
    );
  }
}

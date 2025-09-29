import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import TestSetsGrid from './components/TestSetsGrid';
import TestSetsCharts from './components/TestSetsCharts';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';

export default async function TestSetsPage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(session.session_token);
    const testSetsClient = clientFactory.getTestSetsClient();

    const response = await testSetsClient.getTestSets({
      skip: 0,
      limit: 25,
      sort_by: 'created_at',
      sort_order: 'desc',
    });

    // Now, for each test set with a status_id, fetch status details
    const testSetsWithStatus = await Promise.all(
      response.data.map(async testSet => {
        if (testSet.status_id) {
          try {
            // Use the status client to fetch status details
            const statusClient = clientFactory.getStatusClient();
            const status = await statusClient.getStatus(
              testSet.status_id as string
            );
            return {
              ...testSet,
              status: status.name,
            };
          } catch (error) {
            console.error(
              `Error fetching status for test set ${testSet.id}:`,
              error
            );
            return testSet;
          }
        }
        return testSet;
      })
    );

    return (
      <PageContainer
        title="Test Sets"
        breadcrumbs={[{ title: 'Test Sets', path: '/test-sets' }]}
      >
        {/* Charts Section - Client Component */}
        <TestSetsCharts />

        {/* Table Section */}
        <Paper sx={{ width: '100%', mb: 2, mt: 2 }}>
          <Box sx={{ p: 2 }}>
            <TestSetsGrid
              testSets={testSetsWithStatus}
              loading={false}
              sessionToken={session.session_token}
              initialTotalCount={response.pagination.totalCount}
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
          Error loading test sets: {errorMessage}
        </Typography>
      </Box>
    );
  }
}

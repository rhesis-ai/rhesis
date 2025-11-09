import * as React from 'react';
import { Metadata } from 'next';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import TestSetsGrid from './components/TestSetsGrid';
import TestSetsCharts from './components/TestSetsCharts';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';

export const metadata: Metadata = {
  title: 'Test Sets',
};

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

    // Now, for each test set with a status_id or test_set_type_id, fetch details
    const testSetsWithDetails = await Promise.all(
      response.data.map(async testSet => {
        let updatedTestSet = { ...testSet };

        // Fetch status details if status_id exists
        if (testSet.status_id) {
          try {
            const statusClient = clientFactory.getStatusClient();
            const status = await statusClient.getStatus(
              testSet.status_id as string
            );
            updatedTestSet.status = status.name;
          } catch (error) {
            // Keep original testSet if status fetch fails
          }
        }

        // Fetch test set type details if test_set_type_id exists
        if (testSet.test_set_type_id) {
          try {
            const typeLookupClient = clientFactory.getTypeLookupClient();
            const testSetType = await typeLookupClient.getTypeLookup(
              testSet.test_set_type_id as string
            );
            updatedTestSet.test_set_type = testSetType;
          } catch (error) {
            // Keep original testSet if test set type fetch fails
          }
        }

        return updatedTestSet;
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
              testSets={testSetsWithDetails}
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

import * as React from 'react';
import { Metadata } from 'next';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import TestExplorerGrid from './components/TestExplorerGrid';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';

export const metadata: Metadata = {
  title: 'Test Explorer',
};

export default async function TestExplorerPage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(session.session_token);
    const testSetsClient = clientFactory.getTestSetsClient();

    // Fetch test sets - we'll filter client-side for "Adaptive testing" behavior
    const response = await testSetsClient.getTestSets({
      skip: 0,
      limit: 100,
      sort_by: 'created_at',
      sort_order: 'desc',
    });

    // Filter test sets that have "Adaptive testing" behavior
    const adaptiveTestSets = response.data.filter(testSet => {
      const behaviors = testSet.attributes?.metadata?.behaviors || [];
      return behaviors.includes('Adaptive Testing');
    });

    // Fetch additional details for each test set
    const testSetsWithDetails = await Promise.all(
      adaptiveTestSets.map(async testSet => {
        let updatedTestSet = { ...testSet };

        // Fetch status details if status_id exists
        if (testSet.status_id) {
          try {
            const statusClient = clientFactory.getStatusClient();
            const status = await statusClient.getStatus(
              testSet.status_id as string
            );
            updatedTestSet = { ...updatedTestSet, status: status.name };
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
            updatedTestSet = { ...updatedTestSet, test_set_type: testSetType };
          } catch (error) {
            // Keep original testSet if test set type fetch fails
          }
        }

        return updatedTestSet;
      })
    );

    return (
      <PageContainer title="Test Explorer" breadcrumbs={[]}>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body1" color="text.secondary">
            Explore test sets configured for adaptive testing
          </Typography>
        </Box>

        {/* Table Section */}
        <Paper sx={{ width: '100%', mb: 2 }}>
          <Box sx={{ p: 2 }}>
            <TestExplorerGrid
              testSets={testSetsWithDetails}
              loading={false}
              sessionToken={session.session_token}
              initialTotalCount={testSetsWithDetails.length}
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

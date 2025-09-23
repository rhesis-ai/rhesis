import TestSetDetailCharts from './components/TestSetDetailCharts';
import TestSetTestsGrid from './components/TestSetTestsGrid';
import TestSetDetailsSection from './components/TestSetDetailsSection';
import CommentsWrapper from '@/components/comments/CommentsWrapper'; // Added import
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Box, Grid, Paper, Typography, Button, TextField } from '@mui/material';
import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';
import PlayArrowIcon from '@mui/icons-material/PlayArrowOutlined';
import DownloadIcon from '@mui/icons-material/Download';
import BaseFreesoloAutocomplete from '@/components/common/BaseFreesoloAutocomplete';
import { PaginationParams } from '@/utils/api-client/interfaces/pagination';

interface TestSetsQueryParams extends Partial<PaginationParams> {
  $filter?: string;
}

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// Generate metadata for the page
export async function generateMetadata({ params }: { params: Promise<{ identifier: string }> }): Promise<Metadata> {
  try {
    const resolvedParams = await params;
    const identifier = resolvedParams.identifier;
    const session = await auth() as { session_token: string } | null;
    
    // If no session (like during warmup), return basic metadata
    if (!session?.session_token) {
      return {
        title: `Test Set | ${identifier}`,
        description: `Details for Test Set ${identifier}`,
      };
    }
    
    const apiFactory = new ApiClientFactory(session.session_token);
    const testSetsClient = apiFactory.getTestSetsClient();
    const response = await testSetsClient.getTestSets({ 
      limit: 1,
      $filter: `id eq ${resolvedParams.identifier}`
    } as TestSetsQueryParams);
    const testSet = response.data[0];
    if (!testSet) {
      throw new Error('Test set not found');
    }
    
    return {
      title: testSet.name,
      description: testSet.description || 'Test Set Details',
      // Add other metadata that might be useful
      openGraph: {
        title: testSet.name,
        description: testSet.description || 'Test Set Details',
      },
    };
  } catch (error) {
    return {
      title: 'Test Set Details',
    };
  }
}

export default async function TestSetPage({ params }: { params: any }) {
  // Ensure params is properly awaited
  const resolvedParams = await Promise.resolve(params);
  const identifier = resolvedParams.identifier;
  
  const session = await auth();
  
  // If no session (like during warmup), redirect to login
  if (!session?.session_token) {
    throw new Error('Authentication required');
  }
  
  const apiFactory = new ApiClientFactory(session.session_token);
  const testSetsClient = apiFactory.getTestSetsClient();
  const response = await testSetsClient.getTestSets({ 
    limit: 1,
    $filter: `id eq ${identifier}`
  } as TestSetsQueryParams);
  const testSet = response.data[0];
  if (!testSet) {
    throw new Error('Test set not found');
  }

  // Log the test set data to help diagnose status issues
  console.log('Test Set JSON Data:', JSON.stringify(testSet, null, 2));

  // Serialize the testSet data to ensure consistent rendering
  const serializedTestSet = JSON.parse(JSON.stringify(testSet));

  // Define title and breadcrumbs for PageContainer
  const title = testSet.name || `Test Set ${identifier}`;
  const breadcrumbs = [
    { title: 'Test Sets', path: '/test-sets' },
    { title, path: `/test-sets/${identifier}` }
  ];

  return (
    <PageContainer title={title} breadcrumbs={breadcrumbs}>
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        {/* Charts Section */}
        <Box sx={{ mb: 4 }}>
          <TestSetDetailCharts 
            testSetId={identifier} 
            sessionToken={session.session_token} 
          />
        </Box>

        <Grid container spacing={3}>
          {/* Main Content Column */}
          <Grid item xs={12}>
            <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
              <TestSetDetailsSection 
                testSet={serializedTestSet} 
                sessionToken={session.session_token}
              />
            </Paper>

            {/* Tests Grid Paper */}
            <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
              <TestSetTestsGrid
                testSetId={identifier}
                sessionToken={session.session_token}
              />
            </Paper>

            {/* Tasks and Comments Section */}
            <TasksAndCommentsWrapper
              entityType="TestSet"
              entityId={testSet.id}
              sessionToken={session.session_token}
              currentUserId={session.user?.id || ''}
              currentUserName={session.user?.name || ''}
              currentUserPicture={session.user?.picture || undefined}
            />
          </Grid>

        </Grid>
      </Box>
    </PageContainer>
  );
} 
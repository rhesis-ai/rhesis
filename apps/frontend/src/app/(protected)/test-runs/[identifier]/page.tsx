import { Box, Grid, Paper, Typography } from '@mui/material';
import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestRunDetailCharts from './components/TestRunDetailCharts';
import TestRunTestsGrid from './components/TestRunTestsGrid';
import TestRunDetailsSection from './components/TestRunDetailsSection';
import CommentsWrapper from '@/components/comments/CommentsWrapper';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';

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
        title: `Test Run | ${identifier}`,
        description: `Details for Test Run ${identifier}`,
      };
    }
    
    const apiFactory = new ApiClientFactory(session.session_token);
    const testRunsClient = apiFactory.getTestRunsClient();
    const testRun = await testRunsClient.getTestRun(resolvedParams.identifier);
    
    return {
      title: `Test Run | ${identifier}`,
      description: `Details for Test Run ${identifier}`,
      openGraph: {
        title: `Test Run | ${identifier}`,
        description: `Details for Test Run ${identifier}`,
      },
    };
  } catch (error) {
    return {
      title: 'Test Run Details',
    };
  }
}

export default async function TestRunPage({ params }: { params: any }) {
  // Ensure params is properly awaited
  const resolvedParams = await Promise.resolve(params);
  const identifier = resolvedParams.identifier;
  
  const session = await auth();
  
  // If no session (like during warmup), redirect to login
  if (!session?.session_token) {
    throw new Error('Authentication required');
  }
  
  const apiFactory = new ApiClientFactory(session.session_token);
  const testRunsClient = apiFactory.getTestRunsClient();
  const testRun = await testRunsClient.getTestRun(identifier);

  // Define title and breadcrumbs for PageContainer
  const title = testRun.name || `Test Run ${identifier}`;
  const breadcrumbs = [
    { title: 'Test Runs', path: '/test-runs' },
    { title, path: `/test-runs/${identifier}` }
  ];

  return (
    <PageContainer title={title} breadcrumbs={breadcrumbs}>
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        {/* Charts Section */}
        <Box sx={{ mb: 4 }}>
          <TestRunDetailCharts 
            testRunId={identifier} 
            sessionToken={session.session_token} 
          />
        </Box>

        <Grid container spacing={3}>
          {/* Main Content Column */}
          <Grid item xs={12}>
            <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
              <TestRunDetailsSection 
                testRun={testRun} 
                sessionToken={session.session_token}
              />
            </Paper>

            {/* Tests Grid Paper */}
            <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
              <TestRunTestsGrid
                testRunId={identifier}
                sessionToken={session.session_token}
              />
            </Paper>

            {/* Tasks and Comments Section */}
            <TasksAndCommentsWrapper
              entityType="TestRun"
              entityId={testRun.id}
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
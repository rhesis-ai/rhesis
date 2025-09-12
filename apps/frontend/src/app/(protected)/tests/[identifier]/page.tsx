import * as React from 'react';
import { 
  Typography, 
  Box, 
  Paper, 
  Grid, 
  Divider,
  Button
} from '@mui/material';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import { PageContainer } from '@toolpad/core/PageContainer';
import TestWorkflowSection from './components/TestWorkflowSection';

import TestDetailCharts from './components/TestDetailCharts';
import TestDetailData from './components/TestDetailData';
import TestToTestSet from './components/TestToTestSet';
import TestTags from './components/TestTags';
import CommentsWrapper from '@/components/comments/CommentsWrapper'; // Updated import
import ArrowOutwardIcon from '@mui/icons-material/ArrowOutward';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function TestDetailPage({ params }: PageProps) {
  try {
    // Get session token
    const session = await auth();
    
    if (!session?.session_token) {
      throw new Error('No session token available');
    }
    
    const apiFactory = new ApiClientFactory(session.session_token);
    const testsClient = apiFactory.getTestsClient();
    const promptsClient = apiFactory.getPromptsClient();
    const { identifier } = await params;
    
    // Get test data
    const test = await testsClient.getTest(identifier);
    
    // Get complete prompt data if available
    if (test.prompt_id) {
      const promptData = await promptsClient.getPrompt(test.prompt_id);
      test.prompt = promptData;
    }
    
    // Define title and breadcrumbs for PageContainer
    const content = test.prompt?.content || '';
    const title = content ? (content.length > 45 ?`${content.substring(0, 45)}...` : content) : test.id;
    const breadcrumbs = [
      { title: 'Tests', path: '/tests' },
      { title, path: `/tests/${identifier}` }
    ];
    
    return (
      <PageContainer title={title} breadcrumbs={breadcrumbs}>
        <Box sx={{ flexGrow: 1, pt: 3 }}>
          {/* Charts Section */}
          <Box sx={{ mb: 4 }}>
            <TestDetailCharts 
              testId={identifier} 
              sessionToken={session.session_token} 
            />
          </Box>

          <Grid container spacing={3}>
            {/* Main Content Column */}
            <Grid item xs={12} md={9}>
              <Paper sx={{ p: 3, mb: 4 }}>
                <Grid container spacing={3}>
                  {/* Action Buttons */}
                  <Grid item xs={12}>
                    <TestToTestSet 
                      sessionToken={session.session_token}
                      testId={identifier}
                      parentButton={test.parent_id ? (
                        <Button
                          key="parent-button"
                          component={Link}
                          href={`/tests/${test.parent_id}`}
                          variant="contained"
                          color="primary"
                          startIcon={<ArrowOutwardIcon />}
                        >
                          Go to Parent
                        </Button>
                      ) : undefined}
                    />
                  </Grid>
                  
                  {/* Main Info */}
                  <Grid item xs={12}>
                    <TestDetailData 
                      sessionToken={session.session_token}
                      test={test}
                    />
                  </Grid>
                  
                  {/* Tags Section */}
                  <Grid item xs={12}>
                    <Divider sx={{ my: 2 }} />
                    <TestTags
                      sessionToken={session.session_token}
                      test={test}
                    />
                  </Grid>
                </Grid>
              </Paper>

              {/* Comments Section */}
              <CommentsWrapper
                entityType="Test"
                entityId={test.id}
                sessionToken={session.session_token}
                currentUserId={session.user?.id || ''}
                currentUserName={session.user?.name || ''}
                currentUserPicture={session.user?.picture || undefined}
              />
            </Grid>

            {/* Workflow Column */}
            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Workflow
                </Typography>
                <TestWorkflowSection 
                  sessionToken={session.session_token} 
                  testId={identifier}
                  status={test.status?.name}
                  priority={test.priority}
                  assignee={test.assignee}
                  owner={test.owner}
                />
              </Paper>
            </Grid>
          </Grid>
        </Box>
      </PageContainer>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <PageContainer title="Test Details" breadcrumbs={[{ title: 'Tests', path: '/tests' }]}>
        <Paper sx={{ p: 3 }}>
          <Typography color="error">
            Error loading test details: {errorMessage}
          </Typography>
          <Button 
            component={Link} 
            href="/tests" 
            startIcon={<ArrowBackIcon />}
            sx={{ mt: 2 }}
          >
            Back to Tests
          </Button>
        </Paper>
      </PageContainer>
    );
  }
} 
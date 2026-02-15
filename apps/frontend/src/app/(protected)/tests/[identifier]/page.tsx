import * as React from 'react';
import { Box, Paper, Grid, Divider, Button } from '@mui/material';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import Link from 'next/link';

import { PageContainer } from '@toolpad/core/PageContainer';

import TestDetailCharts from './components/TestDetailCharts';
import TestDetailData from './components/TestDetailData';
import TestToTestSet from './components/TestToTestSet';
import TestTags from './components/TestTags';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import ArrowOutwardIcon from '@mui/icons-material/ArrowOutward';
import { isMultiTurnTest } from '@/constants/test-types';
import { isMultiTurnConfig } from '@/utils/api-client/interfaces/multi-turn-test-config';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// Generate metadata for the page
// Note: We use minimal metadata here to avoid duplicate API calls
// The error boundary will handle 404/410 errors from the main page component
export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  const resolvedParams = await params;
  const identifier = resolvedParams.identifier;

  // Return basic metadata - the page component will fetch data and handle errors
  return {
    title: 'Test Details',
    description: `Details for Test ${identifier}`,
  };
}

export default async function TestDetailPage({ params }: PageProps) {
  // Get session token
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  const apiFactory = new ApiClientFactory(session.session_token);
  const testsClient = apiFactory.getTestsClient();
  const promptsClient = apiFactory.getPromptsClient();
  const { identifier } = await params;

  // Get test data - errors (404, 410, etc.) will be caught by global error.tsx
  const test = await testsClient.getTest(identifier);

  // Get complete prompt data if available
  if (test.prompt_id) {
    const promptData = await promptsClient.getPrompt(test.prompt_id);
    test.prompt = promptData;
  }

  // Define title and breadcrumbs for PageContainer
  // For multi-turn tests, use goal; for single-turn tests, use prompt content
  let content = '';
  if (
    isMultiTurnTest(test.test_type?.type_value) &&
    isMultiTurnConfig(test.test_configuration)
  ) {
    content = test.test_configuration.goal || '';
  } else {
    content = test.prompt?.content || '';
  }

  const title = content
    ? content.length > 45
      ? `${content.substring(0, 45)}...`
      : content
    : test.id;
  const breadcrumbs = [
    { title: 'Tests', path: '/tests' },
    { title, path: `/tests/${identifier}` },
  ];

  // All errors (404, 410, etc.) are caught by the global error.tsx
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
          <Grid size={12}>
            <Paper sx={{ p: 3, mb: 4 }}>
              <Grid container spacing={3}>
                {/* Action Buttons */}
                <Grid size={12}>
                  <TestToTestSet
                    sessionToken={session.session_token}
                    testId={identifier}
                    parentButton={
                      test.parent_id ? (
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
                      ) : undefined
                    }
                  />
                </Grid>

                {/* Main Info */}
                <Grid size={12}>
                  <TestDetailData
                    sessionToken={session.session_token}
                    test={test}
                  />
                </Grid>

                {/* Tags Section */}
                <Grid size={12}>
                  <Divider sx={{ my: 2 }} />
                  <TestTags sessionToken={session.session_token} test={test} />
                </Grid>
              </Grid>
            </Paper>

            {/* Tasks and Comments Section */}
            <TasksAndCommentsWrapper
              entityType="Test"
              entityId={test.id}
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

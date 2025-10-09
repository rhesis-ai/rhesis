import { Box, Typography, Button, Paper } from '@mui/material';
import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestRunMainView from './components/TestRunMainView';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import { UUID } from 'crypto';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// Generate metadata for the page
export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  try {
    const resolvedParams = await params;
    const identifier = resolvedParams.identifier;
    const session = (await auth()) as { session_token: string } | null;

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
  try {
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
    const testResultsClient = apiFactory.getTestResultsClient();
    const promptsClient = apiFactory.getPromptsClient();
    const behaviorClient = apiFactory.getBehaviorClient();

    // Fetch test run details
    const testRun = await testRunsClient.getTestRun(identifier);

    // Fetch all test results for this test run in batches (API limit is 100)
    let testResults: any[] = [];
    let skip = 0;
    const batchSize = 100;
    let hasMore = true;

    while (hasMore) {
      const testResultsResponse = await testResultsClient.getTestResults({
        filter: `test_run_id eq '${identifier}'`,
        limit: batchSize,
        skip: skip,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      testResults = [...testResults, ...testResultsResponse.data];

      // Check if there are more results
      const totalCount = testResultsResponse.pagination?.totalCount || 0;
      hasMore = testResults.length < totalCount;
      skip += batchSize;

      // Safety check to prevent infinite loops
      if (skip > 10000) break;
    }

    // Get unique prompt IDs and fetch prompts
    const promptIds = [
      ...new Set(testResults.filter(r => r.prompt_id).map(r => r.prompt_id!)),
    ];

    // Fetch prompts with error handling for individual failures
    const promptsData = await Promise.allSettled(
      promptIds.map(id => promptsClient.getPrompt(id))
    );

    const promptsMap = promptsData.reduce(
      (acc, result, index) => {
        if (result.status === 'fulfilled') {
          acc[result.value.id] = result.value;
        } else {
          // Log error but continue - use prompt ID as fallback
          console.warn(
            `Failed to fetch prompt ${promptIds[index]}:`,
            result.reason
          );
        }
        return acc;
      },
      {} as Record<string, any>
    );

    // Fetch behaviors with metrics for this test run
    let behaviors: any[] = [];
    try {
      const behaviorsData =
        await testRunsClient.getTestRunBehaviors(identifier);
      const behaviorsWithMetrics = await Promise.all(
        behaviorsData.map(async behavior => {
          try {
            const behaviorMetrics = await (
              behaviorClient as any
            ).getBehaviorMetrics(behavior.id as UUID);
            return {
              ...behavior,
              metrics: behaviorMetrics,
            };
          } catch (error) {
            console.warn(
              `Failed to fetch metrics for behavior ${behavior.id}:`,
              error
            );
            return {
              ...behavior,
              metrics: [],
            };
          }
        })
      );

      behaviors = behaviorsWithMetrics.filter(
        behavior => behavior.metrics.length > 0
      );
    } catch (error) {
      console.warn('Failed to fetch behaviors:', error);
      behaviors = [];
    }

    // Define title and breadcrumbs for PageContainer
    const title = testRun.name || `Test Run ${identifier}`;
    const breadcrumbs = [
      { title: 'Test Runs', path: '/test-runs' },
      { title, path: `/test-runs/${identifier}` },
    ];

    return (
      <PageContainer title={title} breadcrumbs={breadcrumbs}>
        <Box sx={{ flexGrow: 1, pt: 3 }}>
          {/* Main Split View */}
          <div suppressHydrationWarning>
            <TestRunMainView
              testRunId={identifier}
              testRunData={{
                id: testRun.id,
                name: testRun.name,
                created_at:
                  testRun.attributes?.started_at || testRun.created_at || '',
                test_configuration_id: testRun.test_configuration_id,
              }}
              testRun={testRun}
              sessionToken={session.session_token}
              testResults={testResults}
              prompts={promptsMap}
              behaviors={behaviors}
              currentUserId={session.user?.id || ''}
              currentUserName={session.user?.name || ''}
              currentUserPicture={session.user?.picture || undefined}
            />
          </div>
        </Box>
      </PageContainer>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <PageContainer
        title="Test Run Details"
        breadcrumbs={[{ title: 'Test Runs', path: '/test-runs' }]}
      >
        <Paper sx={{ p: 3 }}>
          <Typography color="error">
            Error loading test run details: {errorMessage}
          </Typography>
          <Button
            component={Link}
            href="/test-runs"
            startIcon={<ArrowBackIcon />}
            sx={{ mt: 2 }}
          >
            Back to Test Runs
          </Button>
        </Paper>
      </PageContainer>
    );
  }
}

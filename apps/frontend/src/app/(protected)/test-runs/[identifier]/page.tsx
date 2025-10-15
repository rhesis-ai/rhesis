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
        title: `Test Run ${identifier}`,
        description: `Details for Test Run ${identifier}`,
      };
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const testRunsClient = apiFactory.getTestRunsClient();
    const testRun = await testRunsClient.getTestRun(resolvedParams.identifier);

    return {
      title: testRun.name || identifier,
      description: `Details for Test Run ${testRun.name || identifier}`,
      openGraph: {
        title: testRun.name || identifier,
        description: `Details for Test Run ${testRun.name || identifier}`,
      },
    };
  } catch (error) {
    return {
      title: 'Test Run Details',
    };
  }
}

export default async function TestRunPage({
  params,
  searchParams,
}: {
  params: any;
  searchParams: any;
}) {
  try {
    // Ensure params and searchParams are properly awaited
    const resolvedParams = await Promise.resolve(params);
    const resolvedSearchParams = await Promise.resolve(searchParams);
    const identifier = resolvedParams.identifier;
    const selectedResult = resolvedSearchParams?.selectedresult;
    
    console.log('[TestRunPage] Resolved params:', {
      identifier,
      selectedResult,
      allSearchParams: resolvedSearchParams,
    });

    const session = await auth();

    // If no session (like during warmup), redirect to login
    if (!session?.session_token) {
      throw new Error('Authentication required');
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const testRunsClient = apiFactory.getTestRunsClient();
    const testResultsClient = apiFactory.getTestResultsClient();
    const behaviorClient = apiFactory.getBehaviorClient();

    // Fetch test run details
    const testRun = await testRunsClient.getTestRun(identifier);

    // Fetch all test results for this test run in batches (API limit is 100)
    // The backend now includes nested prompt and behavior objects, eliminating the need for separate API calls
    let testResults: any[] = [];
    let skip = 0;
    const batchSize = 100;
    let hasMore = true;

    while (hasMore) {
      console.log(
        `[SSR] Fetching test results batch: skip=${skip}, limit=${batchSize}`
      );
      const testResultsResponse = await testResultsClient.getTestResults({
        filter: `test_run_id eq '${identifier}'`,
        limit: batchSize,
        skip: skip,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      console.log(
        `[SSR] Received ${testResultsResponse.data.length} test results, total so far: ${testResults.length + testResultsResponse.data.length}`
      );
      testResults = [...testResults, ...testResultsResponse.data];

      // Check if there are more results
      const totalCount = testResultsResponse.pagination?.totalCount || 0;
      hasMore = testResults.length < totalCount;
      skip += batchSize;

      // Safety check to prevent infinite loops
      if (skip > 10000) break;
    }

    // Build prompts map from nested data in test results (optimized - no separate API calls needed!)
    console.log(
      `[SSR] Building prompts map from ${testResults.length} test results using nested data`
    );
    const promptsMap = testResults.reduce(
      (acc, testResult) => {
        // Use nested prompt data if available
        if (testResult.test?.prompt) {
          acc[testResult.test.prompt.id] = {
            id: testResult.test.prompt.id,
            content: testResult.test.prompt.content,
            expected_response: testResult.test.prompt.expected_response,
            nano_id: testResult.test.prompt.nano_id,
            counts: testResult.test.prompt.counts,
          };
        }
        // Fallback: if prompt_id exists but nested data is not available (backward compatibility)
        else if (testResult.prompt_id && !acc[testResult.prompt_id]) {
          console.warn(
            `[SSR] Prompt ${testResult.prompt_id} not found in nested data for test result ${testResult.id}`
          );
        }
        return acc;
      },
      {} as Record<string, any>
    );
    console.log(
      `[SSR] Built prompts map with ${Object.keys(promptsMap).length} unique prompts (NO separate API calls!)`
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
              initialSelectedTestId={selectedResult}
            />
            {selectedResult && (
              <script
                dangerouslySetInnerHTML={{
                  __html: `console.log('[TestRunPage] Rendering with selectedResult:', '${selectedResult}');`,
                }}
              />
            )}
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

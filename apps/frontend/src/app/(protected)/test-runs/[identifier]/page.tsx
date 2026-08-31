import { Metadata } from 'next';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import TestRunMainView from './components/TestRunMainViewClient';
import { prefetch, prefetchList } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import { fetchSmallTestRunResults } from './hooks/test-run-results';
import { hasOtherRunsForTestSet } from './components/comparison-runs';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { emptyFilters, listParams } from '@/utils/list';
import { tracesList } from '@/app/(protected)/traces/components/list';

interface _PageProps {
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
    title: 'Test Run Details',
    description: `Details for Test Run ${identifier}`,
  };
}

export default async function TestRunPage({
  params,
  searchParams,
}: {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const resolvedParams = await Promise.resolve(params);
  const resolvedSearchParams = await Promise.resolve(searchParams);
  const identifier = resolvedParams.identifier;
  const selectedResult = resolvedSearchParams?.selectedresult;
  const detailTab = resolvedSearchParams?.detailTab;

  const session = await requireSession();

  const apiFactory = await createServerApiFactory();
  const testRunsClient = apiFactory.getTestRunsClient();

  // Test results and traces only need `identifier`; only "can compare"
  // needs the fetched test run's test set id.
  const scopedProjectId = (await getServerActiveProjectId()) ?? null;
  const tracesDescriptor = tracesList(scopedProjectId, apiFactory);

  const testResultsPromise = prefetch(Capability.TestResult.READ, () =>
    fetchSmallTestRunResults(apiFactory, identifier)
  );
  const tracesPagePromise = scopedProjectId
    ? prefetchList(tracesDescriptor.capability, () =>
        tracesDescriptor.list(
          apiFactory,
          listParams(tracesDescriptor, {
            page: 1,
            pageSize: tracesDescriptor.defaultPageSize,
            sort: tracesDescriptor.defaultSort,
            filters: {
              ...emptyFilters(tracesDescriptor),
              testRunId: identifier,
            },
          })
        )
      )
    : Promise.resolve({ initialData: undefined, initialTotalCount: 0 });

  let testRun;
  try {
    testRun = await testRunsClient.getTestRun(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  const testSetId = testRun.test_configuration?.test_set?.id;

  const [testResults, hasComparisonRuns, tracesPage] = await Promise.all([
    testResultsPromise,
    testSetId
      ? prefetch(Capability.TestRun.READ, () =>
          hasOtherRunsForTestSet(apiFactory, testSetId, identifier)
        )
      : Promise.resolve(false),
    tracesPagePromise,
  ]);

  // PageLayout is rendered by TestRunMainView, not here: its title carries a
  // rename control and its actions are FABs, both of which need the client
  // component's handlers. Same shape as RequirementsClient.
  return (
    <TestRunMainView
      testRunId={identifier}
      testRunData={{
        id: testRun.id,
        name: testRun.name,
        created_at:
          (typeof testRun.attributes?.started_at === 'string'
            ? testRun.attributes.started_at
            : null) ||
          testRun.created_at ||
          '',
        test_configuration_id: testRun.test_configuration_id,
      }}
      testRun={testRun}
      currentUserId={session.user?.id || ''}
      currentUserName={session.user?.name || ''}
      currentUserPicture={session.user?.picture || undefined}
      initialSelectedTestId={
        typeof selectedResult === 'string' ? selectedResult : undefined
      }
      initialDetailTab={typeof detailTab === 'string' ? detailTab : undefined}
      initialTestResults={testResults}
      initialHasComparisonRuns={hasComparisonRuns}
      initialTraces={tracesPage.initialData}
      initialTracesTotalCount={tracesPage.initialTotalCount}
    />
  );
}

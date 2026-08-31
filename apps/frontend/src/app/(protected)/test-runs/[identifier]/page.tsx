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
import { TAB_KEYS, tabIndexFromKey } from './utils/tab-key';

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

  let testRun;
  try {
    testRun = await testRunsClient.getTestRun(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  // Which tab actually opens first -- same resolution TestRunMainView's own
  // useState initializer runs client-side (see ../utils/tab-key), so the
  // two agree on what "the tab that's opening" means. Everything below is
  // prefetched only for that tab: fetching all three unconditionally used
  // to hold up first paint on two tabs' worth of data the visit doesn't
  // start on.
  const tabParam =
    typeof resolvedSearchParams?.tab === 'string'
      ? resolvedSearchParams.tab
      : null;
  const hasSelectedResult = typeof selectedResult === 'string';
  const initialTabIndex = tabIndexFromKey(
    tabParam,
    hasSelectedResult && !tabParam
  );
  const wantsLinkedEntities =
    initialTabIndex === TAB_KEYS.indexOf('linked_entities');
  const wantsTraces = initialTabIndex === TAB_KEYS.indexOf('traces');

  const scopedProjectId = (await getServerActiveProjectId()) ?? null;
  const tracesDescriptor = tracesList(scopedProjectId, apiFactory);

  const testSetId = testRun.test_configuration?.test_set?.id;

  const [
    testResults,
    verdictMatrix,
    tracesPage,
    testSetExists,
    hasComparisonRuns,
  ] = await Promise.all([
    wantsLinkedEntities
      ? prefetch(Capability.TestResult.READ, () =>
          fetchSmallTestRunResults(apiFactory, identifier)
        )
      : Promise.resolve(undefined),
    // Always: it's what the default Summary tab renders, so unlike the
    // other two this one is never conditional on which tab is opening.
    prefetch(Capability.TestRun.READ, () =>
      testRunsClient.getVerdictMatrix(identifier)
    ),
    wantsTraces && scopedProjectId
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
      : Promise.resolve({ initialData: undefined, initialTotalCount: 0 }),
    testSetId
      ? prefetch(Capability.TestSet.READ, () =>
          apiFactory
            .getTestSetsClient()
            .getTestSet(testSetId)
            .then(() => true)
        )
      : Promise.resolve(false),
    testSetId
      ? prefetch(Capability.TestRun.READ, () =>
          hasOtherRunsForTestSet(apiFactory, testSetId, testRun.id)
        )
      : Promise.resolve(false),
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
      initialVerdictMatrix={verdictMatrix}
      initialTraces={tracesPage.initialData}
      initialTracesTotalCount={tracesPage.initialTotalCount}
      initialTestSetExists={testSetExists ?? undefined}
      initialHasComparisonRuns={hasComparisonRuns ?? false}
    />
  );
}

import { Metadata } from 'next';
import { PageLayout } from '@/components/layout/PageLayout';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import TestRunMainView from './components/TestRunMainViewClient';

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

  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const apiFactory = await createServerApiFactory();
  const testRunsClient = apiFactory.getTestRunsClient();

  let testRun;
  try {
    testRun = await testRunsClient.getTestRun(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  const title = testRun.name || `Test Run ${identifier}`;
  const breadcrumbs = [
    { label: 'Test Runs', href: '/test-runs' },
    { label: title, href: `/test-runs/${identifier}` },
  ];

  return (
    <PageLayout title="" breadcrumbs={breadcrumbs}>
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
      />
    </PageLayout>
  );
}

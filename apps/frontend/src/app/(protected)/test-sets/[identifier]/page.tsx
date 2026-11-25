import * as React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { requireSession } from '@/utils/require-session';
import { format } from 'date-fns';

import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DocumentTitle from '@/components/common/DocumentTitle';
import { detailPageTitle } from '@/utils/document-title';

import TestSetHeaderActions from './components/TestSetHeaderActions';
import TestSetDetailTabs from './components/TestSetDetailTabs';
import TestSetScheduleBanner from './components/TestSetScheduleBanner';
import { testSetTestsList } from './components/list';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function TestSetPage({ params }: PageProps) {
  const session = await requireSession();

  const { identifier } = await params;
  const apiFactory = await createServerApiFactory();
  const testSetsClient = apiFactory.getTestSetsClient();

  // First page of the Tests tab, whose total doubles as the header count. The
  // Test Runs and Tasks tabs fetch their own data when opened.
  const linkedTests = testSetTestsList(identifier);
  const testsPromise = prefetchList(linkedTests.capability, () =>
    linkedTests.list(apiFactory, firstPageParams(linkedTests))
  );

  let testSet;
  try {
    testSet = await testSetsClient.getTestSet(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  const testsPage = await testsPromise;
  const testCount =
    testsPage.initialData !== undefined
      ? testsPage.initialTotalCount
      : (testSet.attributes?.metadata?.total_tests ?? 0);

  const serializedTestSet = JSON.parse(JSON.stringify(testSet));

  const generationStatus = testSet.attributes?.metadata?.generation?.status;
  const isGenerating = generationStatus === 'in_progress';

  const title = testSet.name || `Test Set ${identifier}`;
  const breadcrumbs = [
    { label: 'Test Sets', href: '/test-sets' },
    { label: title, href: `/test-sets/${identifier}` },
  ];

  const isGarakTestSet =
    typeof testSet.attributes?.source === 'string' &&
    testSet.attributes.source === 'garak';

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: testSet.user?.name || '—' },
        {
          label: 'created on:',
          value: testSet.created_at
            ? format(new Date(testSet.created_at), 'dd/MM/yyyy')
            : '—',
        },
      ]}
    />
  );

  const pageActions = (
    <TestSetHeaderActions
      testSetId={identifier}
      testSetName={testSet.name}
      testCount={testCount}
      isGarakTestSet={isGarakTestSet}
    />
  );

  return (
    <PageLayout
      title={title}
      breadcrumbs={breadcrumbs}
      actions={pageActions}
      metadata={metadataStrip}
    >
      <DocumentTitle title={detailPageTitle(testSet.name, 'Test Sets')} />
      <TestSetScheduleBanner testSetId={identifier} />
      <Box sx={{ flexGrow: 1 }}>
        <React.Suspense
          fallback={
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          }
        >
          <TestSetDetailTabs
            testSet={serializedTestSet}
            testCount={testCount}
            initialTests={testsPage.initialData}
            isGenerating={isGenerating}
            currentUserId={session.user?.id || ''}
            currentUserName={session.user?.name || ''}
            currentUserPicture={session.user?.picture || undefined}
          />
        </React.Suspense>
      </Box>
    </PageLayout>
  );
}

import * as React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { format } from 'date-fns';

import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';

import TestSetHeaderActions from './components/TestSetHeaderActions';
import TestSetDetailTabs from './components/TestSetDetailTabs';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  const resolvedParams = await params;
  const identifier = resolvedParams.identifier;
  return {
    title: 'Test Set Details',
    description: `Details for Test Set ${identifier}`,
  };
}

export default async function TestSetPage({ params }: PageProps) {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const apiFactory = await createServerApiFactory(session.session_token);
  const testSetsClient = apiFactory.getTestSetsClient();

  const response = await testSetsClient.getTestSets({
    limit: 1,
    $filter: `id eq ${identifier}`,
  } as {
    limit: number;
    $filter: string;
  });

  let testSet = response.data[0];
  if (!testSet) {
    throw new Error('Test set not found');
  }

  if (testSet.test_set_type_id) {
    try {
      const typeLookupClient = apiFactory.getTypeLookupClient();
      const testSetType = await typeLookupClient.getTypeLookup(
        testSet.test_set_type_id as string
      );
      testSet = { ...testSet, test_set_type: testSetType };
    } catch {
      // keep original if fetch fails
    }
  }

  let testCount = testSet.attributes?.metadata?.total_tests ?? 0;
  try {
    const testsResponse = await testSetsClient.getTestSetTests(identifier, {
      limit: 1,
    });
    testCount = testsResponse.pagination.totalCount;
  } catch {
    // fall back to cached count
  }

  const serializedTestSet = JSON.parse(JSON.stringify(testSet));

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
      sessionToken={session.session_token}
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
            sessionToken={session.session_token}
            currentUserId={session.user?.id || ''}
            currentUserName={session.user?.name || ''}
            currentUserPicture={session.user?.picture || undefined}
          />
        </React.Suspense>
      </Box>
    </PageLayout>
  );
}

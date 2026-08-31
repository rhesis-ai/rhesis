import * as React from 'react';
import { Box, Button, CircularProgress } from '@mui/material';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import { prefetch, prefetchList } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import { fetchTestExecutionHistory } from '@/components/tests/test-execution-history';
import { firstPageParams } from '@/utils/list';
import { linkedTestSetsList } from '@/components/tests/list';
import { entityTasksList } from '@/components/tasks/list';
import Link from 'next/link';
import { format } from 'date-fns';

import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';

import TestToTestSet from './components/TestToTestSet';
import TestDetailTabs from './components/TestDetailTabs';
import ArrowOutwardIcon from '@mui/icons-material/ArrowOutward';
import { isMultiTurnTest } from '@/constants/test-types';
import { isMultiTurnConfig } from '@/utils/api-client/interfaces/multi-turn-test-config';

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
    title: 'Test Details',
    description: `Details for Test ${identifier}`,
  };
}

export default async function TestDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('No session token available');
  }

  const apiFactory = await createServerApiFactory();
  const testsClient = apiFactory.getTestsClient();
  const promptsClient = apiFactory.getPromptsClient();
  const { identifier } = await params;

  // First pages of the Linked Test Sets and Tasks tabs, so they open with
  // rows in place instead of a spinner. These only need `identifier`, so
  // they fetch alongside `getTest` instead of waiting behind it.
  const linkedTestSets = linkedTestSetsList(identifier);
  const tasks = entityTasksList('Test', identifier);
  const tabsPromise = Promise.all([
    prefetchList(linkedTestSets.capability, () =>
      linkedTestSets.list(apiFactory, firstPageParams(linkedTestSets))
    ),
    prefetchList(tasks.capability, () =>
      tasks.list(apiFactory, firstPageParams(tasks))
    ),
    prefetch(Capability.Comment.READ, () =>
      apiFactory.getCommentsClient().getComments('Test', identifier)
    ),
    prefetch(Capability.TestResult.READ, () =>
      fetchTestExecutionHistory(apiFactory, identifier)
    ),
  ]);

  let test;
  try {
    test = await testsClient.getTest(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  if (test.prompt_id) {
    const promptData = await promptsClient.getPrompt(test.prompt_id);
    test.prompt = promptData;
  }

  let content = '';
  if (
    isMultiTurnTest(test.test_type?.type_value) &&
    isMultiTurnConfig(test.test_configuration)
  ) {
    content = test.test_configuration.goal || '';
  } else {
    content = test.prompt?.content || '';
  }

  const [linkedTestSetsPage, tasksPage, comments, executionHistory] =
    await tabsPromise;

  const title = content
    ? content.length > 45
      ? `${content.substring(0, 45)}...`
      : content
    : test.id;

  const breadcrumbs = [
    { label: 'Tests', href: '/tests' },
    { label: title, href: `/tests/${identifier}` },
  ];

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: test.user?.name || '—' },
        {
          label: 'created on:',
          value: test.created_at
            ? format(new Date(test.created_at), 'dd/MM/yyyy')
            : '—',
        },
      ]}
    />
  );

  const pageActions = (
    <TestToTestSet
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
          <TestDetailTabs
            test={test}
            initialLinkedTestSets={linkedTestSetsPage.initialData}
            initialLinkedTestSetsTotalCount={
              linkedTestSetsPage.initialTotalCount
            }
            initialTasks={tasksPage.initialData}
            initialTasksTotalCount={tasksPage.initialTotalCount}
            initialComments={comments}
            initialExecutionHistory={executionHistory}
            currentUserId={session.user?.id || ''}
            currentUserName={session.user?.name || ''}
            currentUserPicture={session.user?.picture || undefined}
          />
        </React.Suspense>
      </Box>
    </PageLayout>
  );
}

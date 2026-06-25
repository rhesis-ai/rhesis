import * as React from 'react';
import { Box, Button, CircularProgress } from '@mui/material';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
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

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  const apiFactory = await createServerApiFactory(session.session_token);
  const testsClient = apiFactory.getTestsClient();
  const promptsClient = apiFactory.getPromptsClient();
  const { identifier } = await params;

  const test = await testsClient.getTest(identifier);

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

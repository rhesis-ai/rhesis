import * as React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { format } from 'date-fns';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import BehaviorDetailTabs from './components/BehaviorDetailTabs';
import type { UUID } from 'crypto';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  const { identifier } = await params;
  return {
    title: 'Behavior Details',
    description: `Details for Behavior ${identifier}`,
  };
}

export default async function BehaviorDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const projectId = await getServerActiveProjectId();
  const client = new BehaviorClient(
    session.session_token,
    undefined,
    projectId
  );

  const behavior = await client.getBehaviorWithMetrics(identifier as UUID);

  if (!behavior) {
    throw new Error('Behavior not found');
  }

  const serializedBehavior = JSON.parse(JSON.stringify(behavior));

  const title = behavior.name || `Behavior ${identifier}`;
  const breadcrumbs = [
    { label: 'Behaviors', href: '/behaviors' },
    { label: title, href: `/behaviors/${identifier}` },
  ];

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: behavior.user?.name || '—' },
        {
          label: 'created on:',
          value: behavior.created_at
            ? format(new Date(behavior.created_at), 'dd/MM/yyyy')
            : '—',
        },
      ]}
    />
  );

  return (
    <PageLayout
      title={title}
      breadcrumbs={breadcrumbs}
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
          <BehaviorDetailTabs
            behavior={serializedBehavior}
            sessionToken={session.session_token}
          />
        </React.Suspense>
      </Box>
    </PageLayout>
  );
}

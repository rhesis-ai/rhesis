'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import { format } from 'date-fns';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import BehaviorDetailTabs from './BehaviorDetailTabs';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface BehaviorDetailClientProps {
  behavior: BehaviorWithMetrics;
  sessionToken: string;
  identifier: string;
}

export default function BehaviorDetailClient({
  behavior: initialBehavior,
  sessionToken,
  identifier,
}: BehaviorDetailClientProps) {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Behavior.READ
  );
  const [behavior, setBehavior] =
    React.useState<BehaviorWithMetrics>(initialBehavior);

  React.useEffect(() => {
    setBehavior(initialBehavior);
  }, [initialBehavior]);

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="behaviors" />;

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
        <BehaviorDetailTabs
          behavior={behavior}
          sessionToken={sessionToken}
          onUpdated={setBehavior}
        />
      </Box>
    </PageLayout>
  );
}

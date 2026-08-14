'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import { format } from 'date-fns';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import { API_ENDPOINTS } from '@/utils/api-client/config';
import RequirementDetailTabs from './RequirementDetailTabs';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface RequirementDetailClientProps {
  requirement: RequirementWithMetrics;
  identifier: string;
}

export default function RequirementDetailClient({
  requirement: initialRequirement,
  identifier,
}: RequirementDetailClientProps) {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Requirement.READ
  );
  const [requirement, setRequirement] =
    React.useState<RequirementWithMetrics>(initialRequirement);

  React.useEffect(() => {
    setRequirement(initialRequirement);
  }, [initialRequirement]);

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="requirements" />;

  const title = requirement.name || `Requirement ${identifier}`;
  const breadcrumbs = [
    { label: 'Requirements', href: API_ENDPOINTS.requirements },
    { label: title, href: `${API_ENDPOINTS.requirements}/${identifier}` },
  ];

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: requirement.user?.name || '—' },
        {
          label: 'created on:',
          value: requirement.created_at
            ? format(new Date(requirement.created_at), 'dd/MM/yyyy')
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
        <RequirementDetailTabs
          requirement={requirement}
          onUpdated={setRequirement}
        />
      </Box>
    </PageLayout>
  );
}

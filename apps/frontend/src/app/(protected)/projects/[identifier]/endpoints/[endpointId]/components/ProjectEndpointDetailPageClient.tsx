'use client';

import { Box, Typography, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DetailEntityMissingState from '@/components/common/DetailEntityMissingState';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EndpointDetailProvider } from '@/app/(protected)/endpoints/[identifier]/components/EndpointDetailContext';
import EndpointDetailView from '@/app/(protected)/endpoints/[identifier]/components/EndpointDetailView';
import EndpointHeaderActions from '@/app/(protected)/endpoints/[identifier]/components/EndpointHeaderActions';
import { useEndpoint, useProject } from '@/hooks/useEndpoints';
import {
  isSessionLoading,
  isSessionUnauthenticated,
} from '@/hooks/useIsAuthenticated';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { Project } from '@/utils/api-client/interfaces/project';

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isValidEndpointId(identifier: string): boolean {
  return !!identifier && UUID_REGEX.test(identifier);
}

interface ProjectEndpointDetailPageClientProps {
  projectId: string;
  endpointId: string;
  /** Server-fetched endpoint; seeds the query so the first paint has content. */
  initialEndpoint?: Endpoint;
  initialProject?: Project;
}

export default function ProjectEndpointDetailPageClient({
  projectId,
  endpointId,
  initialEndpoint,
  initialProject,
}: ProjectEndpointDetailPageClientProps) {
  const router = useRouter();
  const { status } = useSession();
  const isValidId = isValidEndpointId(endpointId);

  const {
    data: endpoint,
    isLoading,
    isFetching,
    error: fetchError,
    refetch,
  } = useEndpoint(endpointId, isValidId, initialEndpoint);
  const { data: project } = useProject(projectId, !!projectId, initialProject);
  const projectName = project?.name ?? '';

  useDocumentTitle(endpoint?.name || null);

  // A seeded endpoint renders straight away; the session check only matters
  // when the client still has to fetch.
  const loading = !endpoint && (isSessionLoading(status) || isLoading);
  const error = !isValidId
    ? 'Invalid endpoint identifier format'
    : fetchError instanceof Error
      ? fetchError.message
      : fetchError
        ? 'Failed to load endpoint'
        : null;

  if (isSessionUnauthenticated(status)) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Authentication required. Please log in.
        </Typography>
      </Box>
    );
  }

  if (loading || (!endpoint && !error)) {
    return (
      <Box
        sx={{
          p: 3,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <CircularProgress size={24} sx={{ mr: 1 }} />
        <Typography>Loading endpoint...</Typography>
      </Box>
    );
  }

  if (fetchError && isNotFoundApiError(fetchError)) {
    return (
      <DetailEntityMissingState
        error={fetchError}
        entityLabel="Endpoint"
        entityId={endpointId}
        entityTableName="endpoint"
        listUrl={`/projects/${projectId}`}
        breadcrumbs={[
          { label: 'Projects', href: '/projects' },
          {
            label: projectName || 'Project',
            href: `/projects/${projectId}`,
          },
          {
            label: 'Not Found',
            href: `/projects/${projectId}/endpoints/${endpointId}`,
          },
        ]}
        onBack={() => router.push(`/projects/${projectId}`)}
        onRetry={() => refetch()}
        isRetrying={isFetching}
      />
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">Error loading endpoint: {error}</Typography>
      </Box>
    );
  }

  if (!endpoint) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">No endpoint found</Typography>
      </Box>
    );
  }

  const breadcrumbs = [
    { label: 'Projects', href: '/projects' },
    {
      label: projectName || 'Project',
      href: `/projects/${projectId}`,
    },
    { label: endpoint.name },
  ];

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: '—' },
        {
          label: 'created on:',
          value: endpoint.endpoint_metadata?.created_at
            ? format(
                new Date(endpoint.endpoint_metadata.created_at),
                'dd/MM/yyyy'
              )
            : '—',
        },
      ]}
    />
  );

  return (
    <EndpointDetailProvider endpoint={endpoint}>
      <PageLayout
        title={endpoint.name}
        breadcrumbs={breadcrumbs}
        metadata={metadataStrip}
        actions={<EndpointHeaderActions />}
      >
        <EndpointDetailView />
      </PageLayout>
    </EndpointDetailProvider>
  );
}

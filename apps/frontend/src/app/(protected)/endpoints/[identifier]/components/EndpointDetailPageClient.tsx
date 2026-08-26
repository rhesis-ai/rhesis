'use client';

import { Box, Typography, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DetailEntityMissingState from '@/components/common/DetailEntityMissingState';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EndpointDetailProvider } from './EndpointDetailContext';
import EndpointDetailView from './EndpointDetailView';
import EndpointHeaderActions from './EndpointHeaderActions';
import { useEndpoint, useProject } from '@/hooks/useEndpoints';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
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

interface EndpointDetailPageClientProps {
  identifier: string;
  /** Server-fetched endpoint; seeds the query so the first paint has content. */
  initialEndpoint?: Endpoint;
  initialProject?: Project;
}

export default function EndpointDetailPageClient({
  identifier,
  initialEndpoint,
  initialProject,
}: EndpointDetailPageClientProps) {
  const router = useRouter();

  const { status } = useSession();

  const isValidId = isValidEndpointId(identifier);

  const {
    data: endpoint,
    isLoading,
    isFetching,
    error: fetchError,
    refetch,
  } = useEndpoint(identifier, isValidId, initialEndpoint);
  const { data: project } = useProject(
    endpoint?.project_id ?? '',
    !!endpoint?.project_id,
    initialProject
  );

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
        entityId={identifier}
        entityTableName="endpoint"
        listUrl="/endpoints"
        breadcrumbs={[
          { label: 'Endpoints', href: '/endpoints' },
          { label: 'Not Found', href: `/endpoints/${identifier}` },
        ]}
        onBack={() => router.push('/endpoints')}
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

  const projectName = project?.name ?? '';
  const endpointWithProject = project
    ? { ...endpoint, project: { ...endpoint.project, name: project.name } }
    : endpoint;

  const breadcrumbs =
    endpoint.project_id && projectName
      ? [
          { label: 'Projects', href: '/projects' },
          { label: projectName, href: `/projects/${endpoint.project_id}` },
          { label: endpoint.name },
        ]
      : [{ label: 'Endpoints', href: '/endpoints' }, { label: endpoint.name }];

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: endpoint.user?.name || '—' },
        {
          label: 'created on:',
          value: endpoint.created_at
            ? format(new Date(endpoint.created_at), 'dd/MM/yyyy')
            : '—',
        },
      ]}
    />
  );

  return (
    <EndpointDetailProvider endpoint={endpointWithProject}>
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

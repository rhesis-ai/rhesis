'use client';

import { Box, Typography, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DetailEntityMissingState from '@/components/common/DetailEntityMissingState';
import { useParams, useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EndpointDetailProvider } from '@/app/(protected)/endpoints/[identifier]/components/EndpointDetailContext';
import EndpointDetailView from '@/app/(protected)/endpoints/[identifier]/components/EndpointDetailView';
import EndpointHeaderActions from '@/app/(protected)/endpoints/[identifier]/components/EndpointHeaderActions';
import { useEndpoint, useProject } from '@/hooks/useEndpoints';
import { isAuthenticated, isSessionLoading, isSessionUnauthenticated } from '@/hooks/useIsAuthenticated';

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function ProjectEndpointPage() {
  const params = useParams<{ identifier: string; endpointId: string }>();
  const router = useRouter();
  const { data: session, status } = useSession();
  const sessionToken = session?.session_token ?? '';
  const isValidId = !!params?.endpointId && UUID_REGEX.test(params.endpointId);

  const {
    data: endpoint,
    isLoading,
    isFetching,
    error: fetchError,
    refetch,
  } = useEndpoint(
    sessionToken,
    params?.endpointId ?? '',
    isAuthenticated(status) && isValidId
  );
  const { data: project } = useProject(
    sessionToken,
    params?.identifier ?? '',
    !!params?.identifier
  );
  const projectName = project?.name ?? '';

  useDocumentTitle(endpoint?.name || null);
  const loading = isSessionLoading(status) || isLoading;
  const error = !isValidId
    ? 'Invalid endpoint identifier format'
    : fetchError instanceof Error
      ? fetchError.message
      : fetchError
        ? 'Failed to load endpoint'
        : null;

  if (isSessionLoading(status) || loading || !params?.endpointId) {
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

  if (isSessionUnauthenticated(status)) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Authentication required. Please log in.
        </Typography>
      </Box>
    );
  }

  if (fetchError && isNotFoundApiError(fetchError) && params?.endpointId) {
    return (
      <DetailEntityMissingState
        error={fetchError}
        entityLabel="Endpoint"
        entityId={params.endpointId}
        entityTableName="endpoint"
        listUrl={`/projects/${params.identifier}`}
        breadcrumbs={[
          { label: 'Projects', href: '/projects' },
          {
            label: projectName || 'Project',
            href: `/projects/${params.identifier}`,
          },
          {
            label: 'Not Found',
            href: `/projects/${params.identifier}/endpoints/${params.endpointId}`,
          },
        ]}
        onBack={() => router.push(`/projects/${params.identifier}`)}
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
      href: `/projects/${params.identifier}`,
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

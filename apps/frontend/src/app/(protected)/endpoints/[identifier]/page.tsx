'use client';

import { Box, Typography, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DetailEntityMissingState from '@/components/common/DetailEntityMissingState';
import { use } from 'react';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EndpointDetailProvider } from './components/EndpointDetailContext';
import EndpointDetailView from './components/EndpointDetailView';
import EndpointHeaderActions from './components/EndpointHeaderActions';
import { useEndpoint, useProject } from '@/hooks/useEndpoints';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
import {
  isSessionLoading,
  isSessionUnauthenticated,
} from '@/hooks/useIsAuthenticated';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function EndpointPage({ params }: PageProps) {
  const { identifier } = use(params);
  const router = useRouter();

  const { status } = useSession();

  const isValidId = !!identifier && UUID_REGEX.test(identifier);

  const {
    data: endpoint,
    isLoading,
    isFetching,
    error: fetchError,
    refetch,
  } = useEndpoint(identifier, isValidId);
  const { data: project } = useProject(
    endpoint?.project_id ?? '',
    !!endpoint?.project_id
  );

  useDocumentTitle(endpoint?.name || null);

  const loading = isSessionLoading(status) || isLoading;
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

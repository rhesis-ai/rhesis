'use client';

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Box, Typography, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DetailNotFoundState from '@/components/common/DetailNotFoundState';
import { use } from 'react';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EndpointDetailProvider } from './components/EndpointDetailContext';
import EndpointDetailView from './components/EndpointDetailView';
import EndpointHeaderActions from './components/EndpointHeaderActions';
import { useQuery } from '@tanstack/react-query';
import { endpointKeys } from '@/constants/query-keys';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function EndpointPage({ params }: PageProps) {
  const { identifier } = use(params);
  const router = useRouter();

  const { data: session, status } = useSession();
  const sessionToken = session?.session_token ?? '';

  const isValidId = !!identifier && UUID_REGEX.test(identifier);

  const {
    data: endpoint,
    isLoading,
    isFetching,
    error: fetchError,
    refetch,
  } = useQuery({
    queryKey: endpointKeys.detail(identifier),
    queryFn: async () => {
      const apiFactory = new ApiClientFactory(sessionToken);
      const data = await apiFactory
        .getEndpointsClient()
        .getEndpoint(identifier);
      if (data.project_id) {
        try {
          const project = await apiFactory
            .getProjectsClient()
            .getProject(data.project_id);
          return { ...data, project: { ...data.project, name: project.name } };
        } catch {
          // project name is non-critical; proceed with endpoint data as-is
        }
      }
      return data;
    },
    enabled: status === 'authenticated' && !!sessionToken && isValidId,
  });

  useDocumentTitle(endpoint?.name || null);

  const loading = status === 'loading' || isLoading;
  const error = !isValidId
    ? 'Invalid endpoint identifier format'
    : fetchError instanceof Error
      ? fetchError.message
      : fetchError
        ? 'Failed to load endpoint'
        : null;

  if (status === 'unauthenticated') {
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
      <DetailNotFoundState
        entityLabel="Endpoint"
        entityId={identifier}
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

  const projectName = endpoint.project?.name ?? '';

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

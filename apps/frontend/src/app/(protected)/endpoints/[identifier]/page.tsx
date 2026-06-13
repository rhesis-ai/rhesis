'use client';

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Box, Typography, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import { use, useEffect, useState } from 'react';
import { format } from 'date-fns';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EndpointDetailProvider } from './components/EndpointDetailContext';
import EndpointDetailView from './components/EndpointDetailView';
import EndpointHeaderActions from './components/EndpointHeaderActions';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default function EndpointPage({ params }: PageProps) {
  const { identifier } = use(params);

  const { data: session, status } = useSession();
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);
  const [projectName, setProjectName] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useDocumentTitle(endpoint?.name || null);

  useEffect(() => {
    const fetchEndpoint = async () => {
      try {
        if (status === 'loading') return;
        if (!identifier) return;

        if (!session) {
          throw new Error('No session available');
        }

        const uuidRegex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(identifier)) {
          throw new Error('Invalid endpoint identifier format');
        }

        const sessionToken = session.session_token || '';
        const apiFactory = new ApiClientFactory(sessionToken);
        const endpointsClient = apiFactory.getEndpointsClient();
        const data = await endpointsClient.getEndpoint(identifier);
        setEndpoint(data);

        if (data.project_id) {
          try {
            const projectsClient = apiFactory.getProjectsClient();
            const project = await projectsClient.getProject(data.project_id);
            setProjectName(project.name);
            setEndpoint(prev =>
              prev
                ? { ...prev, project: { ...prev.project, name: project.name } }
                : prev
            );
          } catch (projectErr) {
            console.error(
              '[EndpointPage] Failed to fetch project name:',
              projectErr
            );
          }
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    fetchEndpoint();
  }, [identifier, session, status]);

  if (status === 'unauthenticated') {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Authentication required. Please log in.
        </Typography>
      </Box>
    );
  }

  if (status === 'loading' || loading || !identifier || (!endpoint && !error)) {
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

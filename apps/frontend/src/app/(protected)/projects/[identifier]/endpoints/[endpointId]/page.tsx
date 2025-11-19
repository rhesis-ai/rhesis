'use client';

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import EndpointDetail from '../../../endpoints/components/EndpointDetail';
import { Box, Typography, CircularProgress } from '@mui/material';
import { PageContainer } from '@toolpad/core';
import { useEffect, useState } from 'react';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useParams } from 'next/navigation';

export default function EndpointPage() {
  const params = useParams<{ identifier: string; endpointId: string }>();
  const { data: session, status } = useSession();
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);
  const [projectName, setProjectName] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Set document title dynamically
  useDocumentTitle(endpoint?.name || null);

  useEffect(() => {
    const fetchEndpoint = async () => {
      try {
        if (status === 'loading') return; // Wait for session to load
        if (!params?.endpointId) return; // Wait for endpointId to be available

        if (!session) {
          throw new Error('No session available');
        }

        // Add UUID validation
        const uuidRegex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(params.endpointId)) {
          throw new Error('Invalid endpoint identifier format');
        }

        // Get session token from the correct property
        const sessionToken = session.session_token || '';
        const apiFactory = new ApiClientFactory(sessionToken);
        const endpointsClient = apiFactory.getEndpointsClient();
        const data = await endpointsClient.getEndpoint(params.endpointId);
        setEndpoint(data);

        // Fetch project name using the identifier from URL
        if (params.identifier) {
          try {
            const projectsClient = apiFactory.getProjectsClient();
            const project = await projectsClient.getProject(params.identifier);
            setProjectName(project.name);
          } catch (error) {
            console.error('Error fetching project:', error);
          }
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    fetchEndpoint();
  }, [params?.endpointId, params?.identifier, session, status]);

  if (status === 'loading' || loading || !params?.endpointId) {
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

  if (status === 'unauthenticated') {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Authentication required. Please log in.
        </Typography>
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

  const breadcrumbs = [
    { title: 'Projects', path: '/projects' },
    {
      title: projectName || 'Project',
      path: `/projects/${params.identifier}`,
    },
    { title: endpoint.name },
  ];

  return (
    <PageContainer title={endpoint.name} breadcrumbs={breadcrumbs}>
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <EndpointDetail endpoint={endpoint} />
      </Box>
    </PageContainer>
  );
}

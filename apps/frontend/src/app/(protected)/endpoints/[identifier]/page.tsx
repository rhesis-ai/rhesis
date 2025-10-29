'use client';

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import EndpointDetail from '../components/EndpointDetail';
import { Box, Typography, CircularProgress } from '@mui/material';
import { PageContainer } from '@toolpad/core';
import { useEffect, useState } from 'react';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useSession } from 'next-auth/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

// Update the interface to match Next.js generated types
interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default function EndpointPage({ params }: PageProps) {
  // Use the params Promise
  const [identifier, setIdentifier] = useState<string>('');

  useEffect(() => {
    // Resolve the params Promise when component mounts
    params.then(resolvedParams => {
      setIdentifier(resolvedParams.identifier);
    });
  }, [params]);

  const { data: session, status } = useSession();
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Set document title dynamically
  useDocumentTitle(endpoint?.name || null);

  useEffect(() => {
    const fetchEndpoint = async () => {
      try {
        if (status === 'loading') return; // Wait for session to load
        if (!identifier) return; // Wait for identifier to be resolved

        if (!session) {
          throw new Error('No session available');
        }

        // Add UUID validation
        const uuidRegex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(identifier)) {
          throw new Error('Invalid endpoint identifier format');
        }

        // Get session token from the correct property
        const sessionToken = session.session_token || '';
        const apiFactory = new ApiClientFactory(sessionToken);
        const endpointsClient = apiFactory.getEndpointsClient();
        const data = await endpointsClient.getEndpoint(identifier);
        setEndpoint(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    fetchEndpoint();
  }, [identifier, session, status]);

  if (status === 'loading' || loading || !identifier) {
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

  return (
    <PageContainer
      title={endpoint.name}
      breadcrumbs={[
        { title: 'Endpoints', path: '/endpoints' },
        { title: endpoint.name },
      ]}
    >
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <EndpointDetail endpoint={endpoint} />
      </Box>
    </PageContainer>
  );
}

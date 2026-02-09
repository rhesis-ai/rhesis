'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import { Box } from '@mui/material';
import EndpointsGrid from './components/EndpointsGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useSession } from 'next-auth/react';
import { useState, useCallback } from 'react';
import { GridPaginationModel } from '@mui/x-data-grid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

export default function EndpointsPage() {
  const { data: session } = useSession();
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  const fetchEndpoints = useCallback(async () => {
    if (!session?.session_token) {
      setError('No session token available');
      return;
    }

    try {
      setLoading(true);
      const skip = paginationModel.page * paginationModel.pageSize;
      const apiFactory = new ApiClientFactory(session.session_token);
      const endpointsClient = apiFactory.getEndpointsClient();
      const response = await endpointsClient.getEndpoints({
        skip,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      setEndpoints(response.data);
      setTotalCount(response.pagination.totalCount);
      setError(null);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [session, paginationModel]);

  const handleEndpointDeleted = useCallback(() => {
    fetchEndpoints();
  }, [fetchEndpoints]);

  React.useEffect(() => {
    fetchEndpoints();
  }, [fetchEndpoints]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">Error loading endpoints: {error}</Typography>
      </Box>
    );
  }

  return (
    <PageContainer title="Endpoints" breadcrumbs={[]}>
      <Box sx={{ mb: 3 }}>
        <Typography color="text.secondary">
          Connect the Rhesis platform to your application under test via
          endpoints to enable comprehensive testing and evaluation workflows.
        </Typography>
      </Box>
      <EndpointsGrid
        endpoints={endpoints}
        loading={loading}
        totalCount={totalCount}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        onEndpointDeleted={handleEndpointDeleted}
      />
    </PageContainer>
  );
}

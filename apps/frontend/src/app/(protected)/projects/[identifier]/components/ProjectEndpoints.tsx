'use client';

import * as React from 'react';
import { useState, useCallback, useEffect } from 'react';
import { Box, Typography } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { GridPaginationModel } from '@mui/x-data-grid';
import EndpointsGrid from '../../../endpoints/components/EndpointsGrid';

interface ProjectEndpointsProps {
  projectId: string;
  sessionToken: string;
}

export default function ProjectEndpoints({
  projectId,
  sessionToken,
}: ProjectEndpointsProps) {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  const fetchEndpoints = useCallback(async () => {
    if (!sessionToken) {
      setError('No session token available');
      return;
    }

    try {
      setLoading(true);
      const skip = paginationModel.page * paginationModel.pageSize;
      const apiFactory = new ApiClientFactory(sessionToken);
      const endpointsClient = apiFactory.getEndpointsClient();
      const response = await endpointsClient.getEndpoints({
        skip,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      // Filter endpoints by project_id on the client side
      const filteredEndpoints = response.data.filter(
        (endpoint: Endpoint) => endpoint.project_id === projectId
      );

      setEndpoints(filteredEndpoints);
      setTotalCount(filteredEndpoints.length);
      setError(null);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel, projectId]);

  useEffect(() => {
    fetchEndpoints();
  }, [fetchEndpoints]);

  const handleEndpointDeleted = useCallback(() => {
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
    <EndpointsGrid
      endpoints={endpoints}
      loading={loading}
      totalCount={totalCount}
      paginationModel={paginationModel}
      onPaginationModelChange={handlePaginationModelChange}
      onEndpointDeleted={handleEndpointDeleted}
      projectId={projectId}
    />
  );
}

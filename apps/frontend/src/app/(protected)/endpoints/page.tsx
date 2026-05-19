'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import { Box } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EndpointsGrid from './components/EndpointsGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab } from '@/components/common/Fab';
import { Toolbar } from '@/components/layout/Toolbar';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useState, useCallback } from 'react';
import { GridPaginationModel } from '@mui/x-data-grid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

export default function EndpointsPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
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
    <PageLayout
      title="Endpoints"
      breadcrumbs={[]}
      actions={
        <Fab
          icon={<AddIcon />}
          tooltip="New Endpoint"
          onClick={() => router.push('/endpoints/new')}
        />
      }
    >
      <Box sx={{ mb: 3 }}>
        <Typography color="text.secondary">
          Connect the Rhesis platform to your application under test via
          endpoints to enable comprehensive testing and evaluation workflows.
        </Typography>
      </Box>
      <Toolbar
        searchProps={{
          value: searchQuery,
          onChange: setSearchQuery,
          placeholder: 'Search endpoints…',
        }}
      />
      <EndpointsGrid
        endpoints={endpoints}
        loading={loading}
        totalCount={totalCount}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        onEndpointDeleted={handleEndpointDeleted}
      />
    </PageLayout>
  );
}

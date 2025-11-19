'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import { Box } from '@mui/material';
import EndpointsGrid from './components/EndpointsGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useSession } from 'next-auth/react';
import { useState, useCallback, useEffect } from 'react';
import { GridPaginationModel } from '@mui/x-data-grid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';

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
  const { markStepComplete, progress } = useOnboarding();

  // Enable tour for this page
  useOnboardingTour('endpoint');

  // Mark step as complete when user clicks the new endpoint button
  // (checked when they navigate to the create page)
  useEffect(() => {
    const checkNavigation = () => {
      // If user navigates away or clicks the button, mark as complete
      if (!progress.endpointSetup) {
        markStepComplete('endpointSetup');
      }
    };

    // Listen for when the "New Endpoint" button is clicked
    const button = document.querySelector(
      '[data-tour="create-endpoint-button"]'
    );
    if (button) {
      button.addEventListener('click', checkNavigation);
      return () => {
        button.removeEventListener('click', checkNavigation);
      };
    }
  }, [progress.endpointSetup, markStepComplete]);

  // Also mark complete when user has endpoints (fallback)
  useEffect(() => {
    if (endpoints.length > 0 && !progress.endpointSetup) {
      markStepComplete('endpointSetup');
    }
  }, [endpoints.length, progress.endpointSetup, markStepComplete]);

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
    <PageContainer title="Endpoints" breadcrumbs={[{ title: 'Endpoints' }]}>
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

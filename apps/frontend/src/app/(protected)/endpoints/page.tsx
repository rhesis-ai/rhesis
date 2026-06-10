'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { ApiIcon } from '@/components/icons';
import EndpointsGrid from './components/EndpointsGrid';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export default function EndpointsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [endpointCount, setEndpointCount] = React.useState<number | null>(null);

  useDocumentTitle('Endpoints');

  const sessionToken = session?.session_token ?? '';

  React.useEffect(() => {
    const fetchCount = async () => {
      if (!sessionToken) return;
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const endpointsClient = apiFactory.getEndpointsClient();
        const response = await endpointsClient.getEndpoints({
          skip: 0,
          limit: 1,
          sort_by: 'created_at',
          sort_order: 'desc',
        });
        setEndpointCount(response.pagination?.totalCount ?? 0);
      } catch {
        setEndpointCount(0);
      }
    };
    fetchCount();
  }, [sessionToken, refreshKey]);

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleCreate = React.useCallback(() => {
    router.push('/endpoints/new');
  }, [router]);

  if (status === 'loading') {
    return (
      <PageLayout title="Endpoints" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!sessionToken) {
    return (
      <PageLayout title="Endpoints" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Endpoints"
      description="Connect the Rhesis platform to your application under test via endpoints to enable comprehensive testing and evaluation workflows."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Fab
            icon={<FabAddIcon />}
            tooltip="New Endpoint"
            onClick={handleCreate}
            data-tour="create-endpoint-button"
          />
        </FabGroup>
      }
    >
      <Box sx={{ mt: 2, mb: 2 }}>
        {endpointCount === 0 ? (
          <EntityEmptyState
            icon={ApiIcon}
            title="No endpoints yet"
            description="Create your first endpoint to connect your application under test and start running tests and evaluations."
            actionLabel="Create endpoint"
            onAction={handleCreate}
          />
        ) : (
          <Paper
            sx={{
              width: '100%',
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              overflow: 'hidden',
            }}
          >
            <EndpointsGrid
              sessionToken={sessionToken}
              refreshKey={refreshKey}
              onRefresh={handleRefresh}
            />
          </Paper>
        )}
      </Box>
    </PageLayout>
  );
}

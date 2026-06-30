'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import EndpointsIcon from '@/components/EndpointsIcon';
import EndpointsGrid from './components/EndpointsGrid';
import EndpointCreateDrawer from './components/EndpointCreateDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';

export default function EndpointsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const canRead = useCan(Capability.Endpoint.READ);
  const canCreate = useCan(Capability.Endpoint.CREATE);
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [endpointCount, setEndpointCount] = React.useState<number | null>(null);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [createProjectId, setCreateProjectId] = React.useState<
    string | undefined
  >();

  useDocumentTitle('Endpoints');

  const sessionToken = session?.session_token ?? '';

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  React.useEffect(() => {
    if (searchParams.get('create') !== '1') return;

    const projectId = searchParams.get('projectId') ?? undefined;
    setCreateProjectId(projectId || undefined);
    setCreateDrawerOpen(true);
    router.replace('/endpoints', { scroll: false });
  }, [searchParams, router]);

  const handleCreate = React.useCallback(() => {
    setCreateProjectId(undefined);
    setCreateDrawerOpen(true);
  }, []);

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setCreateProjectId(undefined);
    handleRefresh();
  }, [handleRefresh]);

  if (status === 'loading') {
    return (
      <PageLayout title="Endpoints" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!canRead) return <AccessDenied resource="endpoints" />;

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
    <>
      <PageLayout
        title="Endpoints"
        description="Connect the Rhesis platform to your application under test via endpoints to enable comprehensive testing and evaluation workflows."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Can capability={Capability.Endpoint.CREATE}>
              <Fab
                icon={<FabAddIcon />}
                tooltip="New Endpoint"
                onClick={handleCreate}
                data-tour="create-endpoint-button"
              />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          {endpointCount === 0 ? (
            <EntityEmptyState
              card
              icon={EndpointsIcon}
              title="No endpoints yet"
              description="Create your first endpoint to connect your application under test and start running tests and evaluations."
              actionLabel={canCreate ? 'Create endpoint' : undefined}
              onAction={canCreate ? handleCreate : undefined}
              enrichment={getEntityEmptyStateEnrichment('endpoints')}
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
                onTotalCountChange={setEndpointCount}
              />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <EndpointCreateDrawer
        open={createDrawerOpen}
        onClose={() => {
          setCreateDrawerOpen(false);
          setCreateProjectId(undefined);
        }}
        onCreated={handleCreateSuccess}
        projectId={createProjectId}
      />
    </>
  );
}

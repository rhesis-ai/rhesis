'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useSession } from 'next-auth/react';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { useBulkActionsBridge } from '@/hooks/useBulkActionsBridge';
import EndpointsGrid from './EndpointsGrid';
import EndpointCreateDrawer from './EndpointCreateDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';
import { useInvalidateUsage } from '@/hooks/useInvalidateUsage';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';

interface EndpointsPageClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Endpoint[];
  initialTotalCount?: number;
}

export default function EndpointsPageClient({
  initialData,
  initialTotalCount = 0,
}: EndpointsPageClientProps) {
  const { status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Endpoint.READ
  );
  const canCreate = useCan(Capability.Endpoint.CREATE);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [createProjectId, setCreateProjectId] = React.useState<
    string | undefined
  >();
  const [refreshTrigger, setRefreshTrigger] = React.useState(0);
  const { bulkActionsVisible, onBulkDelete, handleBulkActionsChange } =
    useBulkActionsBridge();

  useDocumentTitle('Endpoints');

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

  const invalidateUsage = useInvalidateUsage();

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setCreateProjectId(undefined);
    setRefreshTrigger(prev => prev + 1);
    // Endpoints are a stock resource, so the cached /usage count is now stale.
    invalidateUsage();
  }, [invalidateUsage]);

  if (isSessionLoading(status)) {
    return (
      <PageLayout title="Endpoints" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="endpoints" />;

  if (!isAuthenticated(status)) {
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
            {bulkActionsVisible && (
              <Can capability={Capability.Endpoint.DELETE}>
                <Fab
                  icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
                  tooltip="Delete Endpoints"
                  aria-label="Delete Endpoints"
                  onClick={onBulkDelete}
                  sx={{
                    bgcolor: 'error.main',
                    '&:hover': { bgcolor: 'error.dark' },
                  }}
                />
              </Can>
            )}
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
          <EndpointsGrid
            canCreate={canCreate}
            onCreateClick={handleCreate}
            onBulkActionsChange={handleBulkActionsChange}
            initialData={initialData}
            initialTotalCount={initialTotalCount}
            refreshTrigger={refreshTrigger}
          />
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

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Box, Skeleton, Typography, useTheme } from '@mui/material';
import { GridColDef } from '@mui/x-data-grid';
import { useSession } from 'next-auth/react';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import EndpointsIcon from '@/components/EndpointsIcon';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { escapeODataValue } from '@/utils/odata-filter';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import { endpointsList } from './list';
import { getProjectIcon } from './endpoint-icon-utils';
import EndpointFilterDrawer, {
  type EndpointFilters,
  EMPTY_ENDPOINT_FILTERS,
  countActiveEndpointFilters,
} from './EndpointFilterDrawer';

interface EndpointsGridProps {
  projectId?: string;
  /**
   * Only supplied by the top-level Endpoints list page. When present, the
   * grid renders a full loading/empty-state experience of its own; when
   * absent (e.g. the embedded Project > Endpoints tab), it renders exactly
   * as before — BaseDataGrid's own loading skeleton and no-rows overlay,
   * unchanged.
   */
  canCreate?: boolean;
  onCreateClick?: () => void;
  onBulkActionsChange?: (actions: BulkDeleteActionsState) => void;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Endpoint[];
  initialTotalCount?: number;
  /** Bumped by the page after a create succeeds, to trigger a re-fetch. */
  refreshTrigger?: number;
}

function toFilters(state: EntityGridFilterState<EndpointFilters>) {
  return {
    search: state.search,
    connectionType: state.drawer.connectionType,
    environment: state.drawer.environment,
    status: state.drawer.status,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<EndpointFilters> = {
  empty: EMPTY_ENDPOINT_FILTERS,
  countActive: countActiveEndpointFilters,
  render: props => (
    <EndpointFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

export default function EndpointsGrid({
  projectId,
  canCreate,
  onCreateClick,
  onBulkActionsChange,
  initialData,
  initialTotalCount,
  refreshTrigger,
}: EndpointsGridProps) {
  const theme = useTheme();
  const { status } = useSession();

  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState(true);

  const extraODataClauses = useMemo(
    () => (projectId ? [`project_id eq '${escapeODataValue(projectId)}'`] : []),
    [projectId]
  );

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoadingProjects(true);
        if (!isAuthenticated(status)) return;

        const client = new ApiClientFactory().getProjectsClient();
        const response = await client.getProjects();
        const projectMap: Record<string, Project> = {};
        const projectsArray = Array.isArray(response)
          ? response
          : response?.data;

        if (Array.isArray(projectsArray)) {
          projectsArray.forEach((project: Project) => {
            if (project?.id) {
              projectMap[project.id] = project;
            }
          });
        }
        setProjects(projectMap);
      } catch {
        // Projects are optional for display
      } finally {
        setLoadingProjects(false);
      }
    };

    if (isAuthenticated(status)) {
      fetchProjects();
    }
  }, [status]);

  const getRowUrl = useCallback(
    (row: Endpoint) =>
      projectId
        ? `/projects/${projectId}/endpoints/${row.id}`
        : `/endpoints/${row.id}`,
    [projectId]
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1.2,
      },
      {
        field: 'connection_type',
        headerName: 'Connection Type',
        flex: 0.7,
        renderCell: params => <GridBadge label={params.value} />,
      },
      {
        field: 'environment',
        headerName: 'Environment',
        flex: 0.8,
        renderCell: params => <GridBadge label={params.value} />,
      },
      {
        field: 'project',
        headerName: 'Project',
        flex: 1,
        sortable: false,
        renderCell: params => {
          const endpoint = params.row as Endpoint;
          const project = endpoint.project_id
            ? projects[endpoint.project_id]
            : undefined;
          // Unresolved project_id means "loading", not "absent".
          const stillResolving =
            loadingProjects && !!endpoint.project_id && !project;

          if (stillResolving) {
            return <Skeleton variant="text" width={120} />;
          }

          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  color: 'primary.main',
                  '& svg': {
                    fontSize: theme.typography.h5.fontSize,
                  },
                }}
              >
                {getProjectIcon(project)}
              </Box>
              <Typography variant="body2">
                {project ? project.name : 'No project'}
              </Typography>
            </Box>
          );
        },
      },
      {
        field: 'status',
        headerName: 'Status',
        flex: 0.7,
        sortable: false,
        renderCell: params => {
          const endpoint = params.row as Endpoint;
          const status = endpoint.status;

          return <GridBadge label={status?.name ?? 'Unknown'} />;
        },
      },
    ],
    [projects, loadingProjects, theme.typography.h5.fontSize]
  );

  // Only the top-level Endpoints page passes `onCreateClick` — that's when
  // this grid owns its own loading/empty presentation and Paper wrapper.
  const isStandalone = onCreateClick !== undefined;

  return (
    <EntityGrid<Endpoint, typeof endpointsList.filters, EndpointFilters>
      descriptor={endpointsList}
      columns={columns}
      toFilters={toFilters}
      emptyState={
        <EntityEmptyState
          card
          icon={EndpointsIcon}
          title="No endpoints yet"
          description="Create your first endpoint to connect your application under test and start running tests and evaluations."
          actionLabel={canCreate ? 'Create endpoint' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
          enrichment={getEntityEmptyStateEnrichment('endpoints')}
        />
      }
      embedded={!isStandalone}
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      extraFilters={extraODataClauses}
      extraLoading={loadingProjects}
      searchPlaceholder="Search endpoints…"
      drawer={drawerAdapter}
      selectionLabel="Select endpoints"
      getRowUrl={getRowUrl}
      onBulkActionsChange={onBulkActionsChange}
      density="comfortable"
      pageSizeOptions={[10, 25, 50]}
      serverSort={false}
    />
  );
}

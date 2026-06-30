'use client';

import React, {
  useState,
  useEffect,
  useCallback,
  useContext,
  useMemo,
} from 'react';
import { useRouter } from 'next/navigation';
import { Box, Typography, useTheme, Alert } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import GridToolbar from '@/components/common/GridToolbar';
import {
  GridFilterModel,
  GridColDef,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { buildEndpointListFilter } from '@/utils/odata-filter';
import EndpointFilterDrawer, {
  type EndpointFilters,
  EMPTY_ENDPOINT_FILTERS,
  hasActiveEndpointFilters,
  countActiveEndpointFilters,
} from './EndpointFilterDrawer';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { getProjectIcon } from './endpoint-icon-utils';
import { useQueryClient } from '@tanstack/react-query';
import { endpointKeys } from '@/constants/query-keys';
import { useGridState } from '@/hooks/useGridState';
import { useGridQuery } from '@/hooks/useGridQuery';

interface EndpointsGridProps {
  sessionToken?: string;
  refreshKey?: number;
  onRefresh?: () => void;
  onTotalCountChange?: (count: number) => void;
  projectId?: string;
}

interface EndpointsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

const DRAWER_FILTER_FIELDS = [
  'connectionType',
  'environment',
  'status',
] as const;

const EndpointsToolbarContext = React.createContext<EndpointsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

function EndpointsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(EndpointsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search endpoints…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      rightContent={
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

export default function EndpointsGrid({
  sessionToken: sessionTokenProp,
  refreshKey,
  onRefresh,
  onTotalCountChange,
  projectId,
}: EndpointsGridProps) {
  const theme = useTheme();
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();
  const queryClient = useQueryClient();

  const sessionToken = sessionTokenProp || session?.session_token || '';

  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] = useState<EndpointFilters>(
    EMPTY_ENDPOINT_FILTERS
  );
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const {
    filterModel,
    paginationModel,
    setPaginationModel,
    handlePaginationModelChange,
    handleFilterModelChange,
  } = useGridState({
    searchQuery,
    applyDrawerFilters: useCallback(
      (prev: GridFilterModel) => {
        const otherItems = prev.items.filter(
          item =>
            !DRAWER_FILTER_FIELDS.includes(
              item.field as (typeof DRAWER_FILTER_FIELDS)[number]
            )
        );
        const drawerItems: typeof prev.items = [];

        if (drawerFilters.connectionType) {
          drawerItems.push({
            field: 'connectionType',
            operator: 'equals',
            value: drawerFilters.connectionType,
          });
        }
        if (drawerFilters.environment) {
          drawerItems.push({
            field: 'environment',
            operator: 'equals',
            value: drawerFilters.environment,
          });
        }
        if (drawerFilters.status) {
          drawerItems.push({
            field: 'status',
            operator: 'equals',
            value: drawerFilters.status,
          });
        }

        const newItems = [...otherItems, ...drawerItems];
        if (
          newItems.length === prev.items.length &&
          newItems.every((it, i) => it === prev.items[i])
        )
          return prev;
        return { ...prev, items: newItems };
      },
      [drawerFilters]
    ),
    initialPageSize: 10,
  });

  const filterString = buildEndpointListFilter(filterModel, projectId);
  const sort_by = 'created_at';
  const sort_order = 'desc';

  const {
    data: endpointsData,
    isLoading: loading,
    error: fetchError,
  } = useGridQuery({
    queryKey: endpointKeys.list(
      filterString,
      paginationModel.page,
      paginationModel.pageSize,
      sort_by,
      sort_order
    ),
    queryFn: () => {
      const client = new ApiClientFactory(sessionToken).getEndpointsClient();
      return client.getEndpoints({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by,
        sort_order,
        ...(filterString && { $filter: filterString }),
      });
    },
    enabled: !!sessionToken,
  });

  const endpoints = endpointsData?.data ?? [];
  const totalCount = endpointsData?.pagination.totalCount ?? 0;
  const error = fetchError ? 'Failed to load endpoints' : null;

  useEffect(() => {
    if (!endpointsData) return;
    const filtersActive =
      filterModel.items.length > 0 ||
      !!searchQuery ||
      hasActiveEndpointFilters(drawerFilters);
    if (!filtersActive) onTotalCountChange?.(totalCount);
  }, [
    endpointsData,
    filterModel.items.length,
    searchQuery,
    drawerFilters,
    onTotalCountChange,
    totalCount,
  ]);

  useEffect(() => {
    if (refreshKey !== undefined && refreshKey > 0)
      queryClient.invalidateQueries({ queryKey: endpointKeys.all() });
  }, [refreshKey, queryClient]);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoadingProjects(true);
        if (!sessionToken) return;

        const client = new ApiClientFactory(sessionToken).getProjectsClient();
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

    if (sessionToken) {
      fetchProjects();
    }
  }, [sessionToken]);

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: endpointKeys.all() });
    onRefresh?.();
  }, [queryClient, onRefresh]);

  const handleDeleteEndpoints = async () => {
    if (!sessionToken || !pendingDeleteId) return;
    const idsToDelete = [pendingDeleteId];

    try {
      setDeleting(true);
      const endpointsClient = new ApiClientFactory(
        sessionToken
      ).getEndpointsClient();

      await Promise.all(
        idsToDelete.map(id => endpointsClient.deleteEndpoint(id))
      );

      setPendingDeleteId(null);
      setDeleteDialogOpen(false);
      handleRefresh();
    } catch {
      notifications.show('Failed to delete endpoints', { severity: 'error' });
    } finally {
      setDeleting(false);
    }
  };

  const handleRowDeleteAction = useCallback((id: string) => {
    setPendingDeleteId(id);
    setDeleteDialogOpen(true);
  }, []);

  const columns: GridColDef[] = useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => {
        router.push(`/endpoints/${id}`);
      },
      onDelete: id => handleRowDeleteAction(id),
    });
    return [
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
        renderCell: params => {
          const endpoint = params.row as Endpoint;
          const project = endpoint.project_id
            ? projects[endpoint.project_id]
            : undefined;

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
        renderCell: params => {
          const endpoint = params.row as Endpoint;
          const status = endpoint.status;

          return <GridBadge label={status?.name ?? 'Unknown'} />;
        },
      },
      actionsCol,
    ];
  }, [projects, theme.typography.h5.fontSize, handleRowDeleteAction, router]);

  const hasActiveDrawerFilters = hasActiveEndpointFilters(drawerFilters);
  const activeFilterCount = countActiveEndpointFilters(drawerFilters);

  const toolbarContextValue = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters,
      activeFilterCount,
    }),
    [searchQuery, hasActiveDrawerFilters, activeFilterCount]
  );

  return (
    <EndpointsToolbarContext.Provider value={toolbarContextValue}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Box sx={{ position: 'relative' }}>
        <BaseDataGrid
          rows={endpoints}
          columns={columns}
          loading={loading || loadingProjects}
          density="comfortable"
          linkPath={
            projectId ? `/projects/${projectId}/endpoints` : '/endpoints'
          }
          linkField="id"
          serverSidePagination={true}
          totalRows={totalCount}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationModelChange}
          pageSizeOptions={[10, 25, 50]}
          serverSideFiltering={true}
          filterModel={filterModel}
          onFilterModelChange={handleFilterModelChange}
          toolbarSlot={EndpointsUnifiedToolbar}
          showToolbar={true}
          disablePaperWrapper={true}
          persistState
          sx={rowActionsHoverSx}
        />

        <DeleteModal
          open={deleteDialogOpen}
          onClose={() => {
            setDeleteDialogOpen(false);
            setPendingDeleteId(null);
          }}
          onConfirm={handleDeleteEndpoints}
          isLoading={deleting}
          title="Delete Endpoint"
          message="Are you sure you want to delete this endpoint? Related data will not be deleted."
          itemType="endpoints"
        />
      </Box>

      <EndpointFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={setDrawerFilters}
      />
    </EndpointsToolbarContext.Provider>
  );
}

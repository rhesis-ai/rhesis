'use client';

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useContext,
  useMemo,
} from 'react';
import { useRouter } from 'next/navigation';
import { Box, Typography, useTheme, Alert, Paper } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import GridToolbar from '@/components/common/GridToolbar';
import SelectionModeToggle from '@/components/common/SelectionModeToggle';
import {
  GridColDef,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid, { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { listParams } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';
import { endpointsList } from './list';
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
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { getProjectIcon } from './endpoint-icon-utils';
import {
  useBulkDelete,
  type BulkDeleteActionsState,
} from '@/hooks/useBulkDelete';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import GridStateGate from '@/components/common/GridStateGate';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import EndpointsIcon from '@/components/EndpointsIcon';

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

interface EndpointsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
  checkboxSelectionMode: boolean;
  setCheckboxSelectionMode: (v: boolean) => void;
}

const EndpointsToolbarContext = React.createContext<EndpointsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
  checkboxSelectionMode: false,
  setCheckboxSelectionMode: () => {},
});

function EndpointsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
    checkboxSelectionMode,
    setCheckboxSelectionMode,
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
          <SelectionModeToggle
            checked={checkboxSelectionMode}
            onChange={setCheckboxSelectionMode}
            label="Select endpoints"
          />
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

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
  const router = useRouter();
  const { status } = useSession();
  const canEditEndpoint = useCan(Capability.Endpoint.UPDATE);
  const canDeleteEndpoint = useCan(Capability.Endpoint.DELETE);

  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] = useState<EndpointFilters>(
    EMPTY_ENDPOINT_FILTERS
  );
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);

  const filters = useMemo(
    () => ({
      search: searchQuery,
      connectionType: drawerFilters.connectionType,
      environment: drawerFilters.environment,
      status: drawerFilters.status,
    }),
    [searchQuery, drawerFilters]
  );

  const extraODataClauses = useMemo(
    () => (projectId ? [`project_id eq '${escapeODataValue(projectId)}'`] : []),
    [projectId]
  );

  const {
    data: endpoints,
    totalCount,
    isLoading: loading,
    error: rawError,
    page,
    rowsPerPage: pageSize,
    onPageChange,
    onRowsPerPageChange,
    refresh,
  } = usePaginatedList<Endpoint>({
    fetchPage: ({ skip, limit }) =>
      endpointsList.list(
        new ApiClientFactory(),
        listParams(
          endpointsList,
          {
            page: skip / limit + 1,
            pageSize: limit,
            sort: endpointsList.defaultSort,
            filters,
          },
          extraODataClauses
        )
      ),
    filterFingerprint: JSON.stringify(filters),
    defaultPageSize: endpointsList.defaultPageSize,
    initialData,
    initialTotalCount,
    enabled: isAuthenticated(status),
    onError: () => setErrorDismissed(false),
  });

  useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);

  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  const paginationModel = useMemo(() => ({ page, pageSize }), [page, pageSize]);
  const handlePaginationModelChange = useCallback(
    (model: { page: number; pageSize: number }) => {
      if (model.pageSize !== pageSize) {
        onRowsPerPageChange(model.pageSize);
      } else {
        onPageChange(model.page);
      }
    },
    [pageSize, onPageChange, onRowsPerPageChange]
  );

  const {
    checkboxSelectionMode,
    setCheckboxSelectionMode,
    selectedRows,
    handleSelectionChange,
    pendingDeleteId,
    deleteModalOpen,
    isDeleting,
    requestDelete,
    confirmDelete,
    cancelDelete,
  } = useBulkDelete({
    bulkDeleteFn: (ids: string[]) =>
      new ApiClientFactory().getEndpointsClient().bulkDeleteEndpoints(ids),
    onSuccess: refresh,
    itemLabelSingular: 'endpoint',
    itemLabelPlural: 'endpoints',
    onBulkActionsChange,
  });

  const isFirstRefreshTrigger = useRef(true);
  useEffect(() => {
    if (isFirstRefreshTrigger.current) {
      isFirstRefreshTrigger.current = false;
      return;
    }
    refresh();
    // Only refreshTrigger (bumped by the page after a create) should re-run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

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

  const columns: GridColDef[] = useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => {
        router.push(`/endpoints/${id}`);
      },
      onDelete: id => requestDelete(id),
      canEdit: () => canEditEndpoint,
      canDelete: () => canDeleteEndpoint,
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
  }, [projects, theme.typography.h5.fontSize, requestDelete, router]);

  const hasActiveDrawerFilters = hasActiveEndpointFilters(drawerFilters);
  const activeFilterCount = countActiveEndpointFilters(drawerFilters);

  const toolbarContextValue = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters,
      activeFilterCount,
      checkboxSelectionMode,
      setCheckboxSelectionMode,
    }),
    [
      searchQuery,
      hasActiveDrawerFilters,
      activeFilterCount,
      checkboxSelectionMode,
      setCheckboxSelectionMode,
    ]
  );

  // Only the top-level Endpoints page passes `onCreateClick` — that's when
  // this grid owns its own loading/empty presentation and Paper wrapper.
  const isStandalone = onCreateClick !== undefined;
  const filtersActive = !!searchQuery || hasActiveDrawerFilters;

  const content = (
    <EndpointsToolbarContext.Provider value={toolbarContextValue}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
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
            checkboxSelectionMode
              ? undefined
              : projectId
                ? `/projects/${projectId}/endpoints`
                : '/endpoints'
          }
          linkField="id"
          serverSidePagination={true}
          totalRows={totalCount}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationModelChange}
          pageSizeOptions={[10, 25, 50]}
          toolbarSlot={EndpointsUnifiedToolbar}
          showToolbar={true}
          disablePaperWrapper={true}
          persistState
          sx={rowActionsHoverSx}
          checkboxSelection={checkboxSelectionMode}
          disableRowSelectionOnClick={checkboxSelectionMode || undefined}
          rowSelectionModel={checkboxSelectionMode ? selectedRows : []}
          onRowSelectionModelChange={
            checkboxSelectionMode ? handleSelectionChange : undefined
          }
        />

        <DeleteModal
          open={deleteModalOpen}
          onClose={cancelDelete}
          onConfirm={confirmDelete}
          isLoading={isDeleting}
          title={pendingDeleteId ? 'Delete Endpoint' : 'Delete Endpoints'}
          message={
            pendingDeleteId
              ? 'Are you sure you want to delete this endpoint? Related data will not be deleted.'
              : `Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'endpoint' : 'endpoints'}? Related data will not be deleted.`
          }
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

  return (
    <GridStateGate
      active={isStandalone}
      data={loading ? null : {}}
      error={error}
      isEmpty={totalCount === 0 && !filtersActive}
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
    >
      {isStandalone ? <Paper sx={GRID_PAPER_SX}>{content}</Paper> : content}
    </GridStateGate>
  );
}

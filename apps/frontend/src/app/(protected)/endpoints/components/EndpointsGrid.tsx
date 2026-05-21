'use client';

import React, {
  useState,
  useEffect,
  useCallback,
  useContext,
  useMemo,
} from 'react';
import { Box, Typography, useTheme, Alert } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import { FilterButton } from '@/components/common/FilterButton';
import {
  GridColDef,
  GridPaginationModel,
  GridRowSelectionModel,
  GridFilterModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import {
  DeleteIcon,
  ContentCopyIcon,
  SmartToyIcon,
  DevicesIcon,
  WebIcon,
  StorageIcon,
  CodeIcon,
} from '@/components/icons';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
import { createEndpoint } from '@/actions/endpoints';
import { useNotifications } from '@/components/common/NotificationContext';
import { SearchPill } from '@/components/common/SearchPill';
import { buildEndpointListFilter } from '@/utils/odata-filter';
import { GREYSCALE } from '@/styles/theme';
import EndpointFilterDrawer, {
  type EndpointFilters,
  EMPTY_ENDPOINT_FILTERS,
  hasActiveEndpointFilters,
} from './EndpointFilterDrawer';
import DataObjectIcon from '@mui/icons-material/DataObject';
import CloudIcon from '@mui/icons-material/Cloud';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import TerminalIcon from '@mui/icons-material/Terminal';
import VideogameAssetIcon from '@mui/icons-material/VideogameAsset';
import ChatIcon from '@mui/icons-material/Chat';
import PsychologyIcon from '@mui/icons-material/Psychology';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import SchoolIcon from '@mui/icons-material/School';
import ScienceIcon from '@mui/icons-material/Science';
import AccountTreeIcon from '@mui/icons-material/AccountTree';

const ICON_MAP: Record<string, React.ComponentType> = {
  SmartToy: SmartToyIcon,
  Devices: DevicesIcon,
  Web: WebIcon,
  Storage: StorageIcon,
  Code: CodeIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  ShoppingCart: ShoppingCartIcon,
  Terminal: TerminalIcon,
  VideogameAsset: VideogameAssetIcon,
  Chat: ChatIcon,
  Psychology: PsychologyIcon,
  Dashboard: DashboardIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon,
};

const getProjectIcon = (project: Project | undefined) => {
  if (!project) {
    return <SmartToyIcon />;
  }
  if (project.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }
  return <SmartToyIcon />;
};

interface EndpointsGridProps {
  sessionToken?: string;
  refreshKey?: number;
  onRefresh?: () => void;
  projectId?: string;
}

interface EndpointsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
}

const DRAWER_FILTER_FIELDS = [
  'connectionType',
  'environment',
  'projectId',
  'status',
] as const;

const EndpointsToolbarContext = React.createContext<EndpointsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
});

function EndpointsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveDrawerFilters,
  } = useContext(EndpointsToolbarContext);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1,
        borderBottom: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        minHeight: 52,
      }}
    >
      <FilterButton
        onClick={openFilterDrawer}
        hasActiveFilters={hasActiveDrawerFilters}
      />

      <SearchPill
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Search endpoints…"
        width={240}
      />

      <Box sx={{ flex: 1 }} />

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <GridToolbarColumnsButton />
        <GridToolbarDensitySelector />
        <GridToolbarExport />
      </Box>
    </Box>
  );
}

export default function EndpointsGrid({
  sessionToken: sessionTokenProp,
  refreshKey,
  onRefresh,
  projectId,
}: EndpointsGridProps) {
  const theme = useTheme();
  const { data: session } = useSession();
  const notifications = useNotifications();

  const sessionToken = sessionTokenProp || session?.session_token || '';

  const [searchQuery, setSearchQuery] = useState('');
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [duplicating, setDuplicating] = useState(false);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] = useState<EndpointFilters>(
    EMPTY_ENDPOINT_FILTERS
  );

  const fetchEndpoints = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);
      const filterString = buildEndpointListFilter(filterModel, projectId);
      const apiFactory = new ApiClientFactory(sessionToken);
      const endpointsClient = apiFactory.getEndpointsClient();
      const response = await endpointsClient.getEndpoints({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
        ...(filterString && { $filter: filterString }),
      });

      setEndpoints(response.data);
      setTotalCount(response.pagination.totalCount);
      setError(null);
    } catch {
      setError('Failed to load endpoints');
      setEndpoints([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel, filterModel, projectId]);

  useEffect(() => {
    fetchEndpoints();
  }, [fetchEndpoints]);

  useEffect(() => {
    if (refreshKey !== undefined && refreshKey > 0) {
      fetchEndpoints();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== 'quickFilter'
      );
      const items = searchQuery
        ? [
            ...otherItems,
            { field: 'quickFilter', operator: 'contains', value: searchQuery },
          ]
        : otherItems;
      return { ...prev, items };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [searchQuery]);

  useEffect(() => {
    setFilterModel(prev => {
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
      if (drawerFilters.projectId && !projectId) {
        drawerItems.push({
          field: 'projectId',
          operator: 'equals',
          value: drawerFilters.projectId,
        });
      }
      if (drawerFilters.status) {
        drawerItems.push({
          field: 'status',
          operator: 'equals',
          value: drawerFilters.status,
        });
      }

      return { ...prev, items: [...otherItems, ...drawerItems] };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [drawerFilters, projectId]);

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

  const handleRowSelectionModelChange = (
    newSelection: GridRowSelectionModel
  ) => {
    setSelectedRows(newSelection);
  };

  const handleFilterModelChange = useCallback((model: GridFilterModel) => {
    setFilterModel(model);
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const handleRefresh = useCallback(() => {
    fetchEndpoints();
    onRefresh?.();
  }, [fetchEndpoints, onRefresh]);

  const handleDeleteEndpoints = async () => {
    if (!sessionToken || selectedRows.length === 0) return;

    try {
      setDeleting(true);
      const endpointsClient = new ApiClientFactory(
        sessionToken
      ).getEndpointsClient();

      await Promise.all(
        selectedRows.map(id => endpointsClient.deleteEndpoint(id as string))
      );

      setSelectedRows([]);
      setDeleteDialogOpen(false);
      handleRefresh();
    } catch {
      notifications.show('Failed to delete endpoints', { severity: 'error' });
    } finally {
      setDeleting(false);
    }
  };

  const handleDuplicateEndpoints = useCallback(async () => {
    if (selectedRows.length === 0) return;

    try {
      setDuplicating(true);
      let successCount = 0;

      for (const rowId of selectedRows) {
        const source = endpoints.find(ep => ep.id === rowId);
        if (!source) continue;

        const {
          id: _id,
          status: _status,
          status_id: _statusId,
          user_id: _userId,
          organization_id: _orgId,
          nano_id: _nanoId,
          created_at: _createdAt,
          updated_at: _updatedAt,
          ...rest
        } = source as Endpoint & Record<string, unknown>;

        const copyMatch = source.name.match(
          /^(.*?)\s*\(Copy(?:\s+(\d+))?\)\s*$/
        );
        let newName: string;
        if (copyMatch) {
          const base = copyMatch[1];
          const currentNum = copyMatch[2] ? parseInt(copyMatch[2], 10) : 1;
          newName = `${base} (Copy ${currentNum + 1})`;
        } else {
          newName = `${source.name} (Copy)`;
        }

        const result = await createEndpoint({
          ...rest,
          name: newName,
        } as Omit<Endpoint, 'id'>);

        if (result.success) {
          successCount++;
        }
      }

      if (successCount > 0) {
        notifications.show(
          `${successCount} endpoint${successCount > 1 ? 's' : ''} duplicated`,
          { severity: 'success' }
        );
        setSelectedRows([]);
        handleRefresh();
      }
    } catch {
      notifications.show('Failed to duplicate endpoints', {
        severity: 'error',
      });
    } finally {
      setDuplicating(false);
    }
  }, [selectedRows, endpoints, notifications, handleRefresh]);

  const getActionButtons = useCallback(() => {
    if (selectedRows.length === 0) return [];

    return [
      {
        label: duplicating
          ? 'Duplicating...'
          : `Duplicate ${selectedRows.length} endpoint${selectedRows.length > 1 ? 's' : ''}`,
        icon: <ContentCopyIcon />,
        variant: 'outlined' as const,
        onClick: handleDuplicateEndpoints,
        disabled: duplicating,
      },
      {
        label: `Delete ${selectedRows.length} endpoint${selectedRows.length > 1 ? 's' : ''}`,
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: () => setDeleteDialogOpen(true),
        disabled: deleting,
      },
    ];
  }, [selectedRows.length, duplicating, deleting, handleDuplicateEndpoints]);

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
    ],
    [projects, theme.typography.h5.fontSize]
  );

  const hasActiveDrawerFilters = hasActiveEndpointFilters(drawerFilters);

  const toolbarContextValue = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters,
    }),
    [searchQuery, hasActiveDrawerFilters]
  );

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <EndpointsToolbarContext.Provider value={toolbarContextValue}>
      <Box sx={{ position: 'relative' }}>
        {selectedRows.length > 0 && (
          <Box
            sx={{
              px: 2,
              py: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              borderBottom: theme =>
                `1px solid ${
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border
                }`,
            }}
          >
            <Typography variant="subtitle1" color="primary">
              {selectedRows.length} selected
            </Typography>
          </Box>
        )}

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
          checkboxSelection
          disableRowSelectionOnClick
          rowSelectionModel={selectedRows}
          onRowSelectionModelChange={handleRowSelectionModelChange}
          serverSideFiltering={true}
          filterModel={filterModel}
          onFilterModelChange={handleFilterModelChange}
          toolbarSlot={EndpointsUnifiedToolbar}
          actionButtons={getActionButtons()}
          showToolbar={true}
          disablePaperWrapper={true}
          persistState
        />

        <DeleteModal
          open={deleteDialogOpen}
          onClose={() => setDeleteDialogOpen(false)}
          onConfirm={handleDeleteEndpoints}
          isLoading={deleting}
          title={`Delete Endpoint${selectedRows.length > 1 ? 's' : ''}`}
          message={`Are you sure you want to delete ${selectedRows.length} endpoint${selectedRows.length > 1 ? 's' : ''}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`}
          itemType="endpoints"
        />
      </Box>

      <EndpointFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={setDrawerFilters}
        hideProjectFilter={!!projectId}
      />
    </EndpointsToolbarContext.Provider>
  );
}

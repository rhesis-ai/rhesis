'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useContext,
  useMemo,
} from 'react';
import {
  GridColDef,
  GridRowParams,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
  GridSortModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Source } from '@/utils/api-client/interfaces/source';
import { Box, Typography, Chip } from '@mui/material';
import { FilterButton } from '@/components/common/FilterButton';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { SearchPill } from '@/components/common/SearchPill';
import { GREYSCALE } from '@/styles/theme';
import styles from '@/styles/Knowledge.module.css';
import { combineSourceFiltersToOData } from '@/utils/odata-filter';
import { ChatIcon } from '@/components/icons';
import {
  formatFileSize,
  formatDate,
  getFileExtension,
} from '@/constants/knowledge';
import SourceFilterDrawer, {
  type SourceFilters,
  EMPTY_SOURCE_FILTERS,
  hasActiveSourceFilters,
} from './SourceFilterDrawer';

interface SourcesGridProps {
  sessionToken: string;
  refreshKey?: number;
  onRefresh?: () => void;
}

interface SourcesToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
}

const SourcesToolbarContext = React.createContext<SourcesToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
});

function SourcesUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveDrawerFilters,
  } = useContext(SourcesToolbarContext);

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
        placeholder="Search sources…"
        width={240}
      />

      <Box sx={{ flex: 1 }} />

      <GridToolbarColumnsButton />
      <GridToolbarDensitySelector />
      <GridToolbarExport />
    </Box>
  );
}

export default function SourcesGrid({
  sessionToken,
  refreshKey,
  onRefresh,
}: SourcesGridProps) {
  const router = useRouter();
  const notifications = useNotifications();

  // Component state
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [sortModel, setSortModel] = useState<GridSortModel>([
    { field: 'created_at', sort: 'desc' },
  ]);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<SourceFilters>(EMPTY_SOURCE_FILTERS);
  const [searchQuery, setSearchQuery] = useState('');

  // Data fetching function
  const fetchSources = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      // Convert filter model to OData filter string
      const filterString = combineSourceFiltersToOData(filterModel);

      // Get sort field and order from sortModel
      const sortField = sortModel[0]?.field || 'created_at';
      const sortOrder = sortModel[0]?.sort || 'desc';

      const apiParams = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: sortField,
        sort_order: sortOrder as 'asc' | 'desc',
        ...(filterString && { $filter: filterString }),
      };

      const response = await sourcesClient.getSources(apiParams);

      setSources(response.data);
      setTotalCount(response.pagination.totalCount);
      setError(null);
    } catch {
      setError('Failed to load knowledge sources');
      setSources([]);
    } finally {
      setLoading(false);
    }
  }, [
    sessionToken,
    paginationModel.page,
    paginationModel.pageSize,
    filterModel,
    sortModel,
  ]);

  // Initial data fetch
  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  useEffect(() => {
    if (refreshKey !== undefined && refreshKey > 0) {
      fetchSources();
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
    const DRAWER_FIELDS = ['source_type.type_value', 'user.name', 'tags'];
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => !DRAWER_FIELDS.includes(item.field ?? '')
      );
      const drawerItems: typeof prev.items = [];
      if (drawerFilters.sourceType) {
        drawerItems.push({
          field: 'source_type.type_value',
          operator: 'equals',
          value: drawerFilters.sourceType,
        });
      }
      if (drawerFilters.creator) {
        drawerItems.push({
          field: 'user.name',
          operator: 'contains',
          value: drawerFilters.creator,
        });
      }
      if (drawerFilters.tag) {
        drawerItems.push({
          field: 'tags',
          operator: 'contains',
          value: drawerFilters.tag,
        });
      }
      return { ...prev, items: [...otherItems, ...drawerItems] };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [drawerFilters]);

  // Handle pagination
  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  // Handle filter change
  const handleFilterModelChange = useCallback((newModel: GridFilterModel) => {
    setFilterModel(newModel);
    // Reset to first page when filters change
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  // Handle sort change
  const handleSortModelChange = useCallback((newModel: GridSortModel) => {
    setSortModel(newModel);
    // Reset to first page when sort changes
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  // Handle selection change
  const handleSelectionChange = useCallback(
    (newSelection: GridRowSelectionModel) => {
      setSelectedRows(newSelection);
    },
    []
  );

  // Handle row click to navigate to preview
  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      const sourceId = String(params.id);
      router.push(`/knowledge/${sourceId}`);
    },
    [router]
  );

  const handleDeleteSources = useCallback(() => {
    setDeleteModalOpen(true);
  }, []);

  const handleDeleteConfirm = async () => {
    if (selectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      // Delete all selected sources
      await Promise.all(
        selectedRows.map(id =>
          sourcesClient.deleteSource(
            String(id) as `${string}-${string}-${string}-${string}-${string}`
          )
        )
      );

      // Show success notification
      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'source' : 'sources'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      setSelectedRows([]);
      fetchSources();
      onRefresh?.();
    } catch {
      notifications.show('Failed to delete sources', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteModalOpen(false);
  };

  const getActionButtons = useCallback(() => {
    if (selectedRows.length === 0) return [];

    return [
      {
        label: 'Delete Sources',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteSources,
      },
    ];
  }, [selectedRows.length, handleDeleteSources]);

  const toolbarContextValue = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters: hasActiveSourceFilters(drawerFilters),
    }),
    [searchQuery, drawerFilters]
  );

  // Column definitions
  const columns: GridColDef[] = React.useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        flex: 2,
        minWidth: 150,
        renderCell: params => {
          const source = params.row as Source;
          return (
            <Typography
              variant="body2"
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {source.title}
            </Typography>
          );
        },
      },
      {
        field: 'description',
        headerName: 'Description',
        flex: 3,
        minWidth: 200,
        renderCell: params => {
          const source = params.row as Source;
          if (!source.description) {
            return null;
          }
          return (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {source.description}
            </Typography>
          );
        },
      },
      {
        field: 'file_type',
        headerName: 'Type',
        flex: 0.6,
        minWidth: 70,
        renderCell: params => {
          const source = params.row as Source;
          const metadata = source.source_metadata || {};

          // Check if source_type exists in metadata (MCP imports like Notion, Slack, etc.)
          if (metadata.source_type) {
            return (
              <Chip
                label={metadata.source_type}
                size="small"
                variant="outlined"
                className={styles.fileTypeChip}
              />
            );
          }

          // Check if this is a Tool source type (API imports with provider)
          if (source.source_type?.type_value === 'Tool' && metadata.provider) {
            // Capitalize the provider name (e.g., "notion" -> "Notion")
            const providerName =
              metadata.provider.charAt(0).toUpperCase() +
              metadata.provider.slice(1);
            return (
              <Chip
                label={providerName}
                size="small"
                variant="outlined"
                className={styles.fileTypeChip}
              />
            );
          }

          // Fall back to file extension for document sources
          const fileExtension = getFileExtension(metadata.original_filename);

          // Return null if file extension is unknown
          if (fileExtension === 'unknown') {
            return null;
          }

          return (
            <Chip
              label={fileExtension.toUpperCase()}
              size="small"
              variant="outlined"
              className={styles.fileTypeChip}
            />
          );
        },
      },
      {
        field: 'file_size',
        headerName: 'Size',
        flex: 0.6,
        minWidth: 70,
        type: 'number',
        renderCell: params => {
          const source = params.row as Source;
          const metadata = source.source_metadata || {};
          const fileSize = metadata.file_size;

          return (
            <Typography variant="body2" color="text.secondary">
              {formatFileSize(fileSize)}
            </Typography>
          );
        },
      },
      {
        field: 'created_at',
        headerName: 'Uploaded',
        flex: 0.8,
        minWidth: 95,
        filterable: false,
        renderCell: params => {
          const source = params.row as Source;

          // Use backend-created timestamp only
          const dateToShow = source.created_at;

          return (
            <Typography variant="body2" color="text.secondary">
              {formatDate(dateToShow)}
            </Typography>
          );
        },
      },
      {
        field: 'user.name',
        headerName: 'Added by',
        flex: 1,
        minWidth: 110,
        sortable: false,
        renderCell: params => {
          const source = params.row as Source;
          // Use top-level user only
          const uploaderName = source.user?.name || source.user?.email;

          if (!uploaderName) {
            return (
              <Typography variant="body2" color="text.secondary">
                Unknown
              </Typography>
            );
          }

          return (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {uploaderName}
            </Typography>
          );
        },
      },
      {
        field: 'counts.comments',
        headerName: 'Comments',
        flex: 0.8,
        minWidth: 95,
        sortable: false,
        filterable: false,
        renderCell: params => {
          const source = params.row as Source;
          const count = source.counts?.comments || 0;
          if (count === 0) return null;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <ChatIcon sx={{ fontSize: 'small', color: 'text.secondary' }} />
              <Typography variant="body2">{count}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'tags',
        headerName: 'Tags',
        flex: 1.5,
        minWidth: 140,
        sortable: false,
        renderCell: params => {
          const source = params.row as Source;
          if (!source.tags || source.tags.length === 0) {
            return null;
          }

          return (
            <Box
              sx={{
                display: 'flex',
                gap: 0.5,
                flexWrap: 'nowrap',
                overflow: 'hidden',
              }}
            >
              {source.tags.slice(0, 2).map((tag, _index) => (
                <Chip
                  key={tag.id}
                  label={tag.name}
                  size="small"
                  variant="filled"
                  color="primary"
                />
              ))}
              {source.tags.length > 2 && (
                <Chip
                  label={`+${source.tags.length - 2}`}
                  size="small"
                  variant="outlined"
                />
              )}
            </Box>
          );
        },
      },
    ],
    []
  );

  if (error) {
    return (
      <Box className={styles.errorContainer}>
        <Typography color="error" variant="h6" gutterBottom>
          Error Loading Sources
        </Typography>
        <Typography color="text.secondary" paragraph>
          {error}
        </Typography>
      </Box>
    );
  }

  return (
    <SourcesToolbarContext.Provider value={toolbarContextValue}>
      {selectedRows.length > 0 && (
        <Box className={styles.selectionInfo}>
          <Typography variant="subtitle1" className={styles.selectionText}>
            {selectedRows.length} sources selected
          </Typography>
        </Box>
      )}

      <BaseDataGrid
        columns={columns}
        rows={sources}
        loading={loading}
        getRowId={row => row.id}
        showToolbar={true}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        filterModel={filterModel}
        onFilterModelChange={handleFilterModelChange}
        sortModel={sortModel}
        onSortModelChange={handleSortModelChange}
        actionButtons={getActionButtons()}
        checkboxSelection
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        serverSidePagination={true}
        serverSideFiltering={true}
        sortingMode="server"
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        disablePaperWrapper={true}
        onRowClick={handleRowClick}
        toolbarSlot={SourcesUnifiedToolbar}
        persistState
      />

      <DeleteModal
        open={deleteModalOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete Sources"
        message={`Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'source' : 'sources'}? This action cannot be undone.`}
        itemType="sources"
      />

      <SourceFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={f => setDrawerFilters(f)}
      />
    </SourcesToolbarContext.Provider>
  );
}

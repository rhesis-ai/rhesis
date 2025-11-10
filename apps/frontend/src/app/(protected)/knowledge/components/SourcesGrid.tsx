'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
  GridSortModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Source } from '@/utils/api-client/interfaces/source';
import { Box, Typography, Chip } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import UploadIcon from '@mui/icons-material/Upload';
import DeleteIcon from '@mui/icons-material/Delete';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import UploadSourceDialog from './UploadSourceDialog';
import styles from '@/styles/Knowledge.module.css';
import { combineSourceFiltersToOData } from '@/utils/odata-filter';
import { ChatIcon } from '@/components/icons';
import {
  FILE_SIZE_CONSTANTS,
  FILE_TYPE_CONSTANTS,
  TEXT_CONSTANTS,
  formatFileSize,
  formatDate,
  getFileExtension,
} from '@/constants/knowledge';

interface SourcesGridProps {
  sessionToken: string;
  onRefresh?: () => void;
}

// Remove the local formatFileSize function since we're importing it

export default function SourcesGrid({
  sessionToken,
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
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

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

  // Handle refresh - called by parent via onRefresh
  useEffect(() => {
    if (onRefresh) {
      fetchSources();
    }
  }, [onRefresh, fetchSources]);

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
    (params: { id: string }) => {
      const sourceId = params.id;
      router.push(`/knowledge/${sourceId}`);
    },
    [router]
  );

  // Handle delete sources
  const handleDeleteSources = () => {
    setDeleteModalOpen(true);
  };

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

      // Clear selection and refresh data
      setSelectedRows([]);
      fetchSources();
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

  // Get action buttons based on selection
  const getActionButtons = useCallback(() => {
    const buttons: Array<{
      label: string;
      icon: React.ReactNode;
      variant: 'text' | 'outlined' | 'contained';
      onClick: () => void;
    }> = [
      {
        label: 'Upload Source',
        icon: <UploadIcon />,
        variant: 'contained' as const,
        onClick: () => {
          setUploadDialogOpen(true);
        },
      },
    ];

    if (selectedRows.length > 0) {
      buttons.push({
        label: 'Delete Sources',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        onClick: handleDeleteSources,
      });
    }

    return buttons;
  }, [selectedRows.length]);

  // Column definitions
  const columns: GridColDef[] = React.useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        width: 160,
        resizable: false,
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
        width: 200,
        resizable: false,
        renderCell: params => {
          const source = params.row as Source;
          if (!source.description) {
            return (
              <Typography
                variant="body2"
                color="text.secondary"
                fontStyle="italic"
              >
                No description
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
              {source.description}
            </Typography>
          );
        },
      },
      {
        field: 'file_type',
        headerName: 'Type',
        width: 70,
        resizable: false,
        renderCell: params => {
          const source = params.row as Source;
          const metadata = source.source_metadata || {};

          const fileExtension = getFileExtension(metadata.original_filename);

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
        width: 70,
        resizable: false,
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
        width: 95,
        resizable: false,
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
        width: 110,
        resizable: false,
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
        width: 95,
        resizable: false,
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
        width: 160,
        resizable: false,
        sortable: false,
        renderCell: params => {
          const source = params.row as Source;
          if (!source.tags || source.tags.length === 0) {
            return null;
          }

          // Handle both string array and Tag object array
          const tagNames =
            typeof source.tags[0] === 'string'
              ? source.tags
              : (source.tags as any[]).map(tag => tag.name);

          return (
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {tagNames.slice(0, 2).map((tagName: string, index: number) => (
                <Chip
                  key={index}
                  label={tagName}
                  size="small"
                  variant="filled"
                  color="primary"
                />
              ))}
              {tagNames.length > 2 && (
                <Chip
                  label={`+${tagNames.length - 2}`}
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
    <>
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
        showToolbar={false}
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

      <UploadSourceDialog
        open={uploadDialogOpen}
        onClose={() => setUploadDialogOpen(false)}
        onSuccess={() => {
          fetchSources();
          setUploadDialogOpen(false);
        }}
        sessionToken={sessionToken}
      />
    </>
  );
}

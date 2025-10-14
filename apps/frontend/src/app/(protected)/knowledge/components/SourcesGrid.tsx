'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Source } from '@/utils/api-client/interfaces/source';
import { Box, Chip, Tooltip, Typography } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import UploadIcon from '@mui/icons-material/Upload';
import DeleteIcon from '@mui/icons-material/Delete';
import { ChatIcon } from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { DeleteButton } from '@/components/common/DeleteButton';
import styles from '@/styles/SourcesGrid.module.css';

interface SourcesGridProps {
  sessionToken: string;
  onRefresh?: () => void;
}

// Helper function to format file size
const formatFileSize = (bytes?: number) => {
  if (!bytes) return 'Unknown';

  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${Math.round((bytes / Math.pow(1024, i)) * 100) / 100} ${sizes[i]}`;
};

// Chip container for tags with overflow handling
const ChipContainer = ({ items }: { items: string[] }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visibleItems, setVisibleItems] = useState<string[]>([]);
  const [remainingCount, setRemainingCount] = useState(0);

  useEffect(() => {
    const calculateVisibleChips = () => {
      if (!containerRef.current || items.length === 0) return;

      const container = containerRef.current;
      const containerWidth = container.clientWidth;
      const tempDiv = document.createElement('div');
      tempDiv.style.visibility = 'hidden';
      tempDiv.style.position = 'absolute';
      document.body.appendChild(tempDiv);

      let totalWidth = 0;
      let visibleCount = 0;

      // Account for potential overflow chip width
      const overflowChip = document.createElement('div');
      overflowChip.innerHTML =
        '<span class="MuiChip-root" style="padding: 0 8px;">+99</span>';
      document.body.appendChild(overflowChip);
      const overflowChipWidth =
        (overflowChip.firstChild as HTMLElement)?.getBoundingClientRect()
          .width || 0;
      overflowChip.remove();

      for (let i = 0; i < items.length; i++) {
        const chip = document.createElement('div');
        chip.innerHTML = `<span class="MuiChip-root" style="padding: 0 8px;">${items[i]}</span>`;
        tempDiv.appendChild(chip);
        const chipWidth =
          (chip.firstChild as HTMLElement)?.getBoundingClientRect().width || 0;

        if (
          totalWidth +
            chipWidth +
            (i < items.length - 1 ? overflowChipWidth : 0) <=
          containerWidth - 16
        ) {
          // 16px for safety margin
          totalWidth += chipWidth + 8; // 8px for gap
          visibleCount++;
        } else {
          break;
        }
      }

      tempDiv.remove();
      setVisibleItems(items.slice(0, visibleCount));
      setRemainingCount(items.length - visibleCount);
    };

    calculateVisibleChips();
    window.addEventListener('resize', calculateVisibleChips);
    return () => window.removeEventListener('resize', calculateVisibleChips);
  }, [items]);

  if (items.length === 0) return '-';

  return (
    <Box ref={containerRef} className={styles.chipContainer}>
      {visibleItems.map((item: string) => (
        <Chip
          key={item}
          label={item}
          size="small"
          variant="outlined"
          className={styles.tagChip}
        />
      ))}
      {remainingCount > 0 && (
        <Tooltip title={items.slice(visibleItems.length).join(', ')} arrow>
          <Chip
            label={`+${remainingCount}`}
            size="small"
            variant="outlined"
            className={styles.overflowChip}
          />
        </Tooltip>
      )}
    </Box>
  );
};

export default function SourcesGrid({
  sessionToken,
  onRefresh,
}: SourcesGridProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isMounted = useRef(true);

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
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  // Data fetching function
  const fetchSources = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      const apiParams = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc' as const,
      };

      const response = await sourcesClient.getSources(apiParams);

      if (isMounted.current) {
        setSources(response.data);
        setTotalCount(response.pagination.totalCount);
        setError(null);
      }
    } catch (error) {
      console.error('Error fetching sources:', error);
      if (isMounted.current) {
        setError('Failed to load knowledge sources');
        setSources([]);
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, [sessionToken, paginationModel]);

  // Fetch data when dependencies change
  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    fetchSources();
    onRefresh?.();
  }, [fetchSources, onRefresh]);

  // Handle pagination
  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  // Handle selection change
  const handleSelectionChange = useCallback(
    (newSelection: GridRowSelectionModel) => {
      setSelectedRows(newSelection);
    },
    []
  );

  // Handle row click to navigate to preview
  const handleRowClick = useCallback(
    (params: any) => {
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
        selectedRows.map(id => sourcesClient.deleteSource(id as any))
      );

      // Show success notification
      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'source' : 'sources'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      // Clear selection and refresh data
      setSelectedRows([]);
      fetchSources();
    } catch (error) {
      console.error('Error deleting sources:', error);
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
  const getActionButtons = () => {
    const buttons = [
      {
        label: 'Upload Source',
        icon: <UploadIcon />,
        variant: 'contained' as const,
        onClick: () => {
          notifications.show('Upload functionality coming soon!', {
            severity: 'info',
          });
        },
      },
    ];

    if (selectedRows.length > 0) {
      buttons.push({
        label: 'Delete Sources',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteSources,
      } as any);
    }

    return buttons;
  };

  // Column definitions
  const columns: GridColDef[] = [
    {
      field: 'title',
      headerName: 'Title',
      width: 300,
      renderCell: params => {
        const source = params.row as Source;

        return (
          <Box className={styles.sourceContent}>
            <Typography variant="body2">{source.title}</Typography>
            {source.description && (
              <Typography
                variant="caption"
                className={styles.sourceDescription}
              >
                {source.description.length > 50
                  ? `${source.description.substring(0, 50)}...`
                  : source.description}
              </Typography>
            )}
          </Box>
        );
      },
    },
    {
      field: 'type',
      headerName: 'Type',
      width: 120,
      renderCell: params => {
        const source = params.row as Source;
        const metadata = source.source_metadata || {};

        // Extract file extension from original filename
        const getFileExtension = (filename?: string) => {
          if (!filename) return 'unknown';

          const ext = filename.split('.').pop()?.toLowerCase();
          if (!ext) return 'unknown';

          // Handle special cases where we want to normalize extensions
          const normalizedExt =
            ext === 'htm' ? 'html' : ext === 'jpeg' ? 'jpg' : ext;

          return normalizedExt;
        };

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
      field: 'size',
      headerName: 'Size',
      width: 100,
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
      width: 120,
      renderCell: params => {
        const source = params.row as Source;

        const formatDate = (dateString: string | null | undefined) => {
          if (!dateString) return 'Unknown';
          try {
            const date = new Date(dateString);
            return isNaN(date.getTime())
              ? 'Invalid date'
              : date.toLocaleDateString();
          } catch {
            return 'Invalid date';
          }
        };

        // Use uploaded_at from source_metadata
        const dateToShow = source.source_metadata?.uploaded_at;

        return (
          <Typography variant="body2" color="text.secondary">
            {formatDate(dateToShow)}
          </Typography>
        );
      },
    },
    {
      field: 'tags',
      headerName: 'Tags',
      width: 200,
      renderCell: params => {
        const source = params.row as Source;
        return <ChipContainer items={source.tags || []} />;
      },
    },
    {
      field: 'counts.comments',
      headerName: 'Comments',
      width: 100,
      sortable: false,
      filterable: false,
      renderCell: params => {
        const source = params.row as Source;
        const count = source.counts?.comments || 0;
        if (count === 0) return null;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <ChatIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="body2">{count}</Typography>
          </Box>
        );
      },
    },
  ];

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
        actionButtons={getActionButtons()}
        checkboxSelection
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        serverSidePagination={true}
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
    </>
  );
}

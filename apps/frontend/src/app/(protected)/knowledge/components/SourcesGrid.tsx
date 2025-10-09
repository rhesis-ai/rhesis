'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Source } from '@/utils/api-client/interfaces/source';
import {
  Box,
  Chip,
  Tooltip,
  Typography,
  IconButton,
  Avatar,
  useTheme,
} from '@mui/material';
import { MenuBookIcon, DescriptionIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';
import TableChartIcon from '@mui/icons-material/TableChart';
import CodeIcon from '@mui/icons-material/Code';
import LanguageIcon from '@mui/icons-material/Language';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import MenuBookOutlinedIcon from '@mui/icons-material/MenuBookOutlined';
import SlideshowIcon from '@mui/icons-material/Slideshow';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { convertGridFilterModelToOData } from '@/utils/odata-filter';

interface SourcesGridProps {
  sessionToken: string;
  onRefresh?: () => void;
}

// Helper function to get file type icon and color
const getFileTypeInfo = (source: Source, theme: any) => {
  const metadata = source.source_metadata || {};
  const fileType = metadata.file_type || 'unknown';

  const typeMap: Record<string, { icon: React.ReactNode; color: string }> = {
    'pdf': { icon: <PictureAsPdfIcon />, color: theme.palette.error.main },
    'docx': { icon: <DescriptionOutlinedIcon />, color: theme.palette.primary.main },
    'txt': { icon: <TextSnippetIcon />, color: theme.palette.text.secondary },
    'csv': { icon: <TableChartIcon />, color: theme.palette.success.main },
    'json': { icon: <CodeIcon />, color: theme.palette.warning.main },
    'html': { icon: <LanguageIcon />, color: theme.palette.secondary.main },
    'xml': { icon: <DescriptionOutlinedIcon />, color: theme.palette.info.main },
    'epub': { icon: <MenuBookOutlinedIcon />, color: theme.palette.error.main },
    'pptx': { icon: <SlideshowIcon />, color: theme.palette.warning.main },
  };

  return typeMap[fileType.toLowerCase()] || {
    icon: <DescriptionOutlinedIcon />,
    color: theme.palette.text.secondary
  };
};

// Helper function to format file size
const formatFileSize = (bytes?: number) => {
  if (!bytes) return 'Unknown';

  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${Math.round(bytes / Math.pow(1024, i) * 100) / 100} ${sizes[i]}`;
};

// Chip container for tags with overflow handling
const ChipContainer = ({ items, theme }: { items: string[]; theme: any }) => {
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

        if (totalWidth + chipWidth + overflowChipWidth > containerWidth) {
          break;
        }

        totalWidth += chipWidth;
        visibleCount++;
      }

      document.body.removeChild(tempDiv);

      setVisibleItems(items.slice(0, visibleCount));
      setRemainingCount(Math.max(0, items.length - visibleCount));
    };

    calculateVisibleChips();
    window.addEventListener('resize', calculateVisibleChips);

    return () => {
      window.removeEventListener('resize', calculateVisibleChips);
    };
  }, [items]);

  if (items.length === 0) {
    return <Typography variant="body2" color="text.secondary">No tags</Typography>;
  }

  return (
    <Box ref={containerRef} sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
      {visibleItems.map((item, index) => (
        <Chip
          key={index}
          label={item}
          size="small"
          variant="outlined"
          sx={{ fontSize: theme.typography.caption.fontSize, height: 24 }}
        />
      ))}
      {remainingCount > 0 && (
        <Chip
          label={`+${remainingCount}`}
          size="small"
          variant="outlined"
          sx={{ fontSize: theme.typography.caption.fontSize, height: 24 }}
        />
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
  const theme = useTheme();
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
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [sourceToDelete, setSourceToDelete] = useState<Source | null>(null);
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

      // Convert filter model to OData filter string
      const filterString = convertGridFilterModelToOData(filterModel);

      const apiParams = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc' as const,
        ...(filterString && { filter: filterString }),
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
  }, [sessionToken, paginationModel, filterModel]);

  // Fetch data when dependencies change
  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    fetchSources();
    onRefresh?.();
  }, [fetchSources, onRefresh]);

  // Handle delete
  const handleDelete = useCallback(async (source: Source) => {
    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      await sourcesClient.deleteSource(source.id);

      notifications.show(
        `Source "${source.title}" deleted successfully`,
        { severity: 'success' }
      );

      // Refresh the grid
      handleRefresh();
    } catch (error) {
      console.error('Error deleting source:', error);
      notifications.show(
        'Failed to delete source. Please try again.',
        { severity: 'error' }
      );
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
      setSourceToDelete(null);
    }
  }, [sessionToken, notifications, handleRefresh]);

  // Handle view source
  const handleViewSource = useCallback((source: Source) => {
    // TODO: Implement source preview modal
    notifications.show('Source preview coming soon!', { severity: 'info' });
  }, [notifications]);

  // Handle download source
  const handleDownloadSource = useCallback((source: Source) => {
    // TODO: Implement file download
    notifications.show('File download coming soon!', { severity: 'info' });
  }, [notifications]);

  // Column definitions
  const columns: GridColDef[] = [
    {
      field: 'title',
      headerName: 'Title',
      width: 300,
      renderCell: (params) => {
        const source = params.row as Source;
        const fileInfo = getFileTypeInfo(source, theme);

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: fileInfo.color,
                fontSize: theme.typography.body1.fontSize,
              }}
            >
              {fileInfo.icon}
            </Avatar>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {source.title}
              </Typography>
              {source.description && (
                <Typography variant="caption" color="text.secondary">
                  {source.description.length > 50
                    ? `${source.description.substring(0, 50)}...`
                    : source.description
                  }
                </Typography>
              )}
            </Box>
          </Box>
        );
      },
    },
    {
      field: 'type',
      headerName: 'Type',
      width: 120,
      renderCell: (params) => {
        const source = params.row as Source;
        const metadata = source.source_metadata || {};
        const fileType = metadata.file_type || 'unknown';

        return (
          <Chip
            label={fileType.toUpperCase()}
            size="small"
            variant="outlined"
            sx={{ textTransform: 'uppercase', fontSize: theme.typography.caption.fontSize }}
          />
        );
      },
    },
    {
      field: 'size',
      headerName: 'Size',
      width: 100,
      renderCell: (params) => {
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
      renderCell: (params) => {
        const source = params.row as Source;
        return (
          <Typography variant="body2" color="text.secondary">
            {new Date(source.created_at).toLocaleDateString()}
          </Typography>
        );
      },
    },
    {
      field: 'tags',
      headerName: 'Tags',
      width: 200,
      renderCell: (params) => {
        const source = params.row as Source;
        return <ChipContainer items={source.tags || []} theme={theme} />;
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const source = params.row as Source;

        return (
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="View">
              <IconButton
                size="small"
                onClick={() => handleViewSource(source)}
              >
                <VisibilityIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Download">
              <IconButton
                size="small"
                onClick={() => handleDownloadSource(source)}
              >
                <DownloadIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete">
              <IconButton
                size="small"
                onClick={() => {
                  setSourceToDelete(source);
                  setDeleteModalOpen(true);
                }}
                color="error"
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        );
      },
    },
  ];

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
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
      <BaseDataGrid
        rows={sources}
        columns={columns}
        loading={loading}
        serverSidePagination={true}
        totalRows={totalCount}
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        rowSelectionModel={selectedRows}
        onRowSelectionModelChange={setSelectedRows}
        pageSizeOptions={[10, 25, 50, 100]}
        checkboxSelection
        disableRowSelectionOnClick
        getRowId={(row) => row.id}
        sx={{
          '& .MuiDataGrid-cell': {
            borderBottom: `1px solid ${theme.palette.divider}`,
          },
          '& .MuiDataGrid-columnHeaders': {
            backgroundColor: theme.palette.grey[50],
            borderBottom: `2px solid ${theme.palette.divider}`,
          },
        }}
      />

      {/* Delete Confirmation Modal */}
      <DeleteModal
        open={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setSourceToDelete(null);
        }}
        onConfirm={() => sourceToDelete && handleDelete(sourceToDelete)}
        title="Delete Source"
        message={
          sourceToDelete
            ? `Are you sure you want to delete "${sourceToDelete.title}"? This action cannot be undone.`
            : ''
        }
        isLoading={isDeleting}
      />
    </>
  );
}

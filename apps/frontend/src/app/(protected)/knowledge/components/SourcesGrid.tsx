'use client';

import React, { useCallback, useMemo } from 'react';
import { GridColDef } from '@mui/x-data-grid';
import { Box, Chip, Typography } from '@mui/material';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { Source } from '@/utils/api-client/interfaces/source';
import { ChatIcon, MenuBookIcon } from '@/components/icons';
import { formatFileSize, getFileExtension } from '@/constants/knowledge';
import { formatDate } from '@/utils/date';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import { sourcesList } from './list';
import SourceFilterDrawer, {
  type SourceFilters,
  EMPTY_SOURCE_FILTERS,
  countActiveSourceFilters,
} from './SourceFilterDrawer';

interface SourcesGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
  onBulkActionsChange?: (actions: BulkDeleteActionsState) => void;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Source[];
  initialTotalCount?: number;
  /** Bumped by the page after an upload/import succeeds, to trigger a re-fetch. */
  refreshTrigger?: number;
}

function toFilters(state: EntityGridFilterState<SourceFilters>) {
  return {
    search: state.search,
    sourceType: state.drawer.sourceType,
    creator: state.drawer.creator,
    tag: state.drawer.tag,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<SourceFilters> = {
  empty: EMPTY_SOURCE_FILTERS,
  countActive: countActiveSourceFilters,
  render: props => (
    <SourceFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

export default function SourcesGrid({
  canCreate,
  onCreateClick,
  onBulkActionsChange,
  initialData,
  initialTotalCount,
  refreshTrigger,
}: SourcesGridProps) {
  const getRowUrl = useCallback((row: Source) => `/knowledge/${row.id}`, []);

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        width: 220,
        minWidth: 160,
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
        width: 300,
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
        width: 100,
        minWidth: 80,
        renderCell: params => {
          const source = params.row as Source;
          const metadata = source.source_metadata || {};

          // MCP imports like Notion, Slack, etc.
          if (metadata.source_type) {
            return <GridBadge label={metadata.source_type} />;
          }

          // Tool source type (API imports with provider)
          if (source.source_type?.type_value === 'Tool' && metadata.provider) {
            const providerName =
              metadata.provider.charAt(0).toUpperCase() +
              metadata.provider.slice(1);
            return <GridBadge label={providerName} />;
          }

          // Fall back to file extension for document sources
          const fileExtension = getFileExtension(metadata.original_filename);

          if (fileExtension === 'unknown') {
            return null;
          }

          return <GridBadge label={fileExtension.toUpperCase()} />;
        },
      },
      {
        field: 'file_size',
        headerName: 'Size',
        width: 80,
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
        width: 110,
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
        width: 140,
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
        width: 100,
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
        width: 160,
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
              {source.tags.slice(0, 2).map(tag => (
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

  return (
    <EntityGrid<Source, typeof sourcesList.filters, SourceFilters>
      descriptor={sourcesList}
      columns={columns}
      toFilters={toFilters}
      emptyState={
        <EntityEmptyState
          card
          icon={MenuBookIcon}
          title="No knowledge sources yet"
          description="Upload files or import from tool connections to use as context for test generation and evaluation."
          actionLabel={canCreate ? 'Upload source' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
        />
      }
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      searchPlaceholder="Search sources…"
      drawer={drawerAdapter}
      selectionLabel="Select sources"
      getRowUrl={getRowUrl}
      onBulkActionsChange={onBulkActionsChange}
      pageSizeOptions={[10, 25, 50]}
    />
  );
}

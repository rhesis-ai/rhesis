'use client';

import React, { useMemo } from 'react';
import Link from 'next/link';
import {
  Box,
  Link as MuiLink,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import type {
  GridColDef,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import SubdirectoryArrowRightIcon from '@mui/icons-material/SubdirectoryArrowRight';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridBadge from '@/components/common/GridBadge';
import { BORDER_RADIUS } from '@/styles/theme';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import {
  completeness,
  orderByHierarchy,
  type HierarchyRow,
} from './requirements-table';

interface RequirementsTableProps {
  requirements: RequirementWithMetrics[];
  loading: boolean;
  totalCount: number;
  page: number;
  rowsPerPage: number;
  onPageChange: (page: number) => void;
  onRowsPerPageChange: (size: number) => void;
}

type TableRow = HierarchyRow & { id: string };

const MAX_TAGS = 2;

function countCell(value: number | undefined) {
  return (
    <Typography
      variant="body2"
      color={value ? 'text.primary' : 'text.secondary'}
    >
      {value ?? 0}
    </Typography>
  );
}

function NameCell({ row }: { row: TableRow }) {
  const { requirement, depth } = row;
  const children = requirement.children_count ?? 0;
  // A child whose parent is on another page says where it belongs.
  const parentNote =
    depth === 0 && requirement.parent?.name
      ? `in ${requirement.parent.name}`
      : null;
  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={0.5}
      sx={{ pl: Math.max(depth - 1, 0) * 3, height: 1, minWidth: 0 }}
    >
      {depth > 0 && (
        <SubdirectoryArrowRightIcon
          fontSize="small"
          sx={{ color: 'text.secondary', flexShrink: 0 }}
          aria-label="Child of the row above"
        />
      )}
      <Stack sx={{ minWidth: 0 }}>
        <MuiLink
          component={Link}
          href={`/requirements/${requirement.id}`}
          underline="hover"
          variant="body2"
          noWrap
          sx={{ fontWeight: depth === 0 ? 600 : 400 }}
          onClick={e => e.stopPropagation()}
        >
          {requirement.name}
        </MuiLink>
        {(children > 0 || parentNote) && (
          <Typography variant="caption" color="text.secondary" noWrap>
            {children > 0
              ? children === 1
                ? '1 child'
                : `${children} children`
              : parentNote}
          </Typography>
        )}
      </Stack>
    </Stack>
  );
}

function CompletenessCell({
  requirement,
}: {
  requirement: RequirementWithMetrics;
}) {
  const dots = completeness(requirement);
  const title = dots
    .map(d => `${d.label}: ${d.done ? 'yes' : 'missing'}`)
    .join(' · ');
  return (
    <Tooltip title={title}>
      <Stack
        direction="row"
        spacing={0.5}
        alignItems="center"
        sx={{ height: 1 }}
        aria-label={title}
      >
        {dots.map(dot => (
          <Box
            key={dot.key}
            sx={theme => ({
              width: theme.spacing(1),
              height: theme.spacing(1),
              borderRadius: BORDER_RADIUS.pill,
              bgcolor: dot.done ? 'primary.main' : 'divider',
            })}
          />
        ))}
      </Stack>
    </Tooltip>
  );
}

/**
 * The requirements list as a table. Same rows, filters and pages as the cards:
 * the parent passes in what `useList` already fetched.
 */
export default function RequirementsTable({
  requirements,
  loading,
  totalCount,
  page,
  rowsPerPage,
  onPageChange,
  onRowsPerPageChange,
}: RequirementsTableProps) {
  const rows: TableRow[] = useMemo(
    () =>
      orderByHierarchy(requirements).map(row => ({
        ...row,
        id: String(row.requirement.id),
      })),
    [requirements]
  );

  const columns = useMemo<GridColDef<TableRow>[]>(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 2,
        minWidth: 220,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) => (
          <NameCell row={row} />
        ),
      },
      {
        field: 'impact',
        headerName: 'Impact',
        width: 160,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) =>
          row.requirement.impact?.type_value ? (
            <GridBadge label={row.requirement.impact.type_value} />
          ) : (
            '—'
          ),
      },
      {
        field: 'complete',
        headerName: 'Complete',
        width: 110,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) => (
          <CompletenessCell requirement={row.requirement} />
        ),
      },
      {
        field: 'sources',
        headerName: 'Sources',
        width: 100,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) =>
          countCell(row.requirement.sources?.length),
      },
      {
        field: 'examples',
        headerName: 'Examples',
        width: 100,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) =>
          countCell(row.requirement.examples_count),
      },
      {
        field: 'tests',
        headerName: 'Tests',
        width: 90,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) =>
          countCell(row.requirement.test_counts?.total),
      },
      {
        field: 'metrics',
        headerName: 'Metrics',
        width: 90,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) =>
          countCell(row.requirement.metrics?.length),
      },
      {
        field: 'tags',
        headerName: 'Tags',
        flex: 1,
        minWidth: 160,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<TableRow>) => {
          const tags = row.requirement.tags ?? [];
          if (tags.length === 0) return '—';
          return (
            <Stack direction="row" spacing={0.5} alignItems="center">
              {tags.slice(0, MAX_TAGS).map(tag => (
                <GridBadge key={tag.id} label={tag.name} />
              ))}
              {tags.length > MAX_TAGS && (
                <GridBadge label={`+${tags.length - MAX_TAGS}`} />
              )}
            </Stack>
          );
        },
      },
    ],
    []
  );

  return (
    <BaseDataGrid
      rows={rows as unknown as GridRowModel[]}
      columns={columns as GridColDef[]}
      loading={loading}
      getRowId={row => String(row.id)}
      getRowUrl={row => `/requirements/${String(row.id)}`}
      serverSidePagination
      totalRows={totalCount}
      paginationModel={{ page, pageSize: rowsPerPage }}
      onPaginationModelChange={model => {
        if (model.page !== page) onPageChange(model.page);
        if (model.pageSize !== rowsPerPage) onRowsPerPageChange(model.pageSize);
      }}
      pageSizeOptions={[25, 50, 100]}
      // Paged by the same TablePagination as the cards, below the grid.
      hideFooter
      disableRowSelectionOnClick
    />
  );
}

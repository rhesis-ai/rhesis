'use client';

import React, { useMemo } from 'react';
import { GridColDef } from '@mui/x-data-grid';
import { Typography, Box, Avatar, Chip, Tooltip } from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import EntityGrid, {
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { PlayArrowIcon } from '@/components/icons';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { passRate } from '@/constants/outcomes';
import { formatDate } from '@/utils/date';
import { asVersionInfo, summarizeVersionInfo } from '@/utils/version-info';
import { testSetRunsList } from './testSetRunsList';

const STATUS_TABS = [
  { label: 'All', value: 'all' },
  { label: 'In Progress', value: 'Progress' },
  { label: 'Completed', value: 'Completed' },
  { label: 'Partial', value: 'Partial' },
  { label: 'Failed', value: 'Failed' },
];

const compactChipSx = {
  height: 20,
  '& .MuiChip-label': { px: 0.75 },
} as const;

type ScopedFilters = { search: string; status: string };

function toFilters(
  state: EntityGridFilterState<Record<string, never>>
): ScopedFilters {
  return { search: state.search, status: state.pill };
}

interface TestSetRunsGridProps {
  testSetId: string;
  initialData?: TestRunDetail[];
  initialTotalCount?: number;
}

export default function TestSetRunsGrid({
  testSetId,
  initialData,
  initialTotalCount,
}: TestSetRunsGridProps) {
  const descriptor = useMemo(() => testSetRunsList(testSetId), [testSetId]);

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1.8,
        minWidth: 120,
        filterable: true,
        valueGetter: (_, row) => row.name || '',
      },
      {
        field: 'total_tests',
        headerName: 'Total Tests',
        flex: 1,
        minWidth: 80,
        align: 'right',
        headerAlign: 'right',
        valueGetter: (_, row) => row?.attributes?.total_tests || 0,
      },
      {
        field: 'pass_rate',
        headerName: 'Pass Rate',
        flex: 1,
        minWidth: 90,
        align: 'right',
        headerAlign: 'right',
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => {
          const stats = row.stats;
          if (!stats) return null;
          return passRate(stats.passed, stats.failed);
        },
        renderCell: params => {
          const value = params.value as number | null;
          if (value === null || value === undefined) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            );
          }
          return <Typography variant="body2">{value.toFixed(1)}%</Typography>;
        },
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        flex: 0,
        minWidth: 90,
        renderCell: params => {
          const status = params.row.status?.name;
          if (!status) return null;
          return <GridBadge label={status} />;
        },
      },
      {
        field: 'version_info',
        headerName: 'Version Information',
        flex: 1.2,
        minWidth: 170,
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => {
          const info = asVersionInfo(row.attributes?.version_info);
          if (!info) return '';
          return summarizeVersionInfo(info)
            .map(entry => `${entry.key}=${entry.display}`)
            .join(' ');
        },
        renderCell: params => {
          const info = asVersionInfo(params.row.attributes?.version_info);
          if (!info) return null;
          const entries = summarizeVersionInfo(info);
          const shown = entries.slice(0, 2);
          const overflow = entries.length - shown.length;

          return (
            <Tooltip
              title={
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    fontSize: theme => theme.typography.caption.fontSize,
                  }}
                >
                  {JSON.stringify(info, null, 2)}
                </Box>
              }
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  overflow: 'hidden',
                }}
              >
                {shown.map(entry => (
                  <Chip
                    key={entry.key}
                    label={`${entry.key}: ${entry.display}`}
                    size="small"
                    variant="outlined"
                    sx={compactChipSx}
                  />
                ))}
                {overflow > 0 && (
                  <Chip
                    label={`+${overflow}`}
                    size="small"
                    variant="outlined"
                    sx={compactChipSx}
                  />
                )}
              </Box>
            </Tooltip>
          );
        },
      },
      {
        field: 'user.name',
        headerName: 'Executor',
        flex: 1.4,
        minWidth: 120,
        filterable: true,
        valueGetter: (_, row) => {
          const executor = row.user;
          if (!executor) return '';
          return (
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email
          );
        },
        renderCell: params => {
          const executor = params.row.user;
          if (!executor) return null;
          const displayName =
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Avatar src={executor.picture} sx={{ width: 24, height: 24 }}>
                <PersonIcon />
              </Avatar>
              <Typography variant="body2">{displayName}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'created_at',
        headerName: 'Created',
        flex: 1.2,
        minWidth: 140,
        filterable: false,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary">
            {formatDate(params.row.created_at)}
          </Typography>
        ),
      },
    ],
    []
  );

  return (
    <EntityGrid<TestRunDetail, typeof descriptor.filters, Record<string, never>>
      descriptor={descriptor}
      columns={columns}
      toFilters={toFilters}
      emptyState={
        <EntityEmptyState
          card
          icon={PlayArrowIcon}
          title="No test runs yet"
          description="Execute this test set against an AI endpoint to see results here."
        />
      }
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      searchPlaceholder="Search test runs…"
      pills={{ tabs: STATUS_TABS }}
      getRowUrl={row => `/test-runs/${row.id}`}
      editAction={false}
      pageSizeOptions={[10, 25, 50]}
    />
  );
}

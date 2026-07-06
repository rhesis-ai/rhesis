'use client';

import React, { useMemo } from 'react';
import { Box, Chip, Typography, useTheme } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import Link from 'next/link';
import { GridColDef } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { formatDate } from '@/utils/date';
import StatusChip from '@/components/common/StatusChip';
import { TestExecutionHistoryRow } from './test-execution-history';

interface TestExecutionHistoryTableProps {
  rows: TestExecutionHistoryRow[];
  highlightTestRunId?: string;
}

export default function TestExecutionHistoryTable({
  rows,
  highlightTestRunId,
}: TestExecutionHistoryTableProps) {
  const theme = useTheme();

  const columns = useMemo<GridColDef[]>(
    () => [
      {
        field: 'passed',
        headerName: 'Status',
        width: 120,
        sortable: false,
        renderCell: params => (
          <StatusChip
            passed={params.row.passed}
            label={params.row.passed ? 'Pass' : 'Fail'}
            size="small"
            variant="outlined"
          />
        ),
      },
      {
        field: 'testRunName',
        headerName: 'Test Run',
        flex: 1,
        minWidth: 220,
        sortable: false,
        renderCell: params => {
          const item = params.row as TestExecutionHistoryRow;

          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {item.testRunId !== 'unknown' ? (
                <Link
                  href={`/test-runs/${item.testRunId}?selectedresult=${item.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: 'none' }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      '&:hover .test-run-name': {
                        color: theme.palette.primary.main,
                        textDecoration: 'underline',
                      },
                    }}
                  >
                    <Typography
                      className="test-run-name"
                      variant="body2"
                      sx={{
                        transition: 'color 0.2s',
                        color: 'text.primary',
                        fontWeight:
                          item.testRunId === highlightTestRunId ? 600 : 400,
                      }}
                    >
                      {item.testRunName}
                    </Typography>
                    <OpenInNewIcon
                      sx={{ fontSize: 14, color: 'text.disabled' }}
                    />
                  </Box>
                </Link>
              ) : (
                <Typography variant="body2" color="text.primary">
                  {item.testRunName}
                </Typography>
              )}
              {highlightTestRunId && item.testRunId === highlightTestRunId && (
                <Chip
                  label="Current"
                  size="small"
                  variant="outlined"
                  sx={{
                    borderColor: 'divider',
                    color: 'text.primary',
                    fontSize: 12,
                  }}
                />
              )}
            </Box>
          );
        },
      },
      {
        field: 'metrics',
        headerName: 'Metrics',
        width: 140,
        sortable: false,
        renderCell: params => {
          const item = params.row as TestExecutionHistoryRow;
          return (
            <Typography variant="body2" color="text.primary">
              {item.passedMetrics}/{item.totalMetrics} passed
            </Typography>
          );
        },
      },
      {
        field: 'executedAt',
        headerName: 'Executed At',
        width: 200,
        sortable: false,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary">
            {formatDate(params.row.executedAt)}
          </Typography>
        ),
      },
    ],
    [highlightTestRunId, theme.palette.primary.main]
  );

  return (
    <BaseDataGrid
      rows={rows}
      columns={columns}
      getRowId={row => row.id}
      disableRowSelectionOnClick
      showToolbar={false}
      disablePaperWrapper
      pageSizeOptions={[10, 25, 50]}
      initialState={{
        pagination: { paginationModel: { pageSize: 10, page: 0 } },
      }}
    />
  );
}

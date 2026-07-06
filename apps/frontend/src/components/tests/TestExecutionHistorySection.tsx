'use client';

import React, { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  Paper,
  TablePagination,
  Typography,
} from '@mui/material';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import TestExecutionHistoryTable from './TestExecutionHistoryTable';
import { useTestExecutionHistory } from './useTestExecutionHistory';

interface TestExecutionHistorySectionProps {
  testId: string;
  sessionToken: string;
}

const PAGE_SIZE_OPTIONS = [10, 25, 50];

export default function TestExecutionHistorySection({
  testId,
  sessionToken,
}: TestExecutionHistorySectionProps) {
  const { rows, loading, error } = useTestExecutionHistory({
    testId,
    sessionToken,
  });
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const paginatedRows = useMemo(() => {
    const start = page * rowsPerPage;
    return rows.slice(start, start + rowsPerPage);
  }, [rows, page, rowsPerPage]);

  if (loading) {
    return (
      <Paper
        elevation={0}
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          py: 8,
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
        }}
      >
        <CircularProgress />
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper
        elevation={0}
        sx={{ p: 3, border: 1, borderColor: 'divider', borderRadius: 2 }}
      >
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  if (rows.length === 0) {
    return (
      <EntityEmptyState
        card
        icon={HistoryOutlinedIcon}
        title="No executions yet"
        description="This test hasn't been run yet. Run it as part of a test set to see execution history here."
      />
    );
  }

  return (
    <Paper
      elevation={0}
      sx={{ p: 3, border: 1, borderColor: 'divider', borderRadius: 2 }}
    >
      <Typography
        variant="h6"
        sx={{ fontWeight: 600, color: 'primary.main', mb: 2 }}
      >
        Execution History ({rows.length})
      </Typography>

      <TestExecutionHistoryTable rows={paginatedRows} testId={testId} />

      {rows.length > PAGE_SIZE_OPTIONS[0] && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <TablePagination
            component="div"
            count={rows.length}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={event => {
              setRowsPerPage(parseInt(event.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={PAGE_SIZE_OPTIONS}
          />
        </Box>
      )}
    </Paper>
  );
}

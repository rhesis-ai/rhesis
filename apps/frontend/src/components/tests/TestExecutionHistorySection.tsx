'use client';

import React from 'react';
import { Alert, Box, CircularProgress, Paper, Typography } from '@mui/material';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import TestExecutionHistoryTable from './TestExecutionHistoryTable';
import { useTestExecutionHistory } from './useTestExecutionHistory';

interface TestExecutionHistorySectionProps {
  testId: string;
  sessionToken: string;
}

export default function TestExecutionHistorySection({
  testId,
  sessionToken,
}: TestExecutionHistorySectionProps) {
  const { rows, loading, error } = useTestExecutionHistory({
    testId,
    sessionToken,
  });

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

      <TestExecutionHistoryTable rows={rows} />
    </Paper>
  );
}

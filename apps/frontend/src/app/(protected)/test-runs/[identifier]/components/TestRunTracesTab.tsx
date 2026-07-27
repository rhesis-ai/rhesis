'use client';

import React, { useCallback, useState } from 'react';
import { Box, Paper } from '@mui/material';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import TracesClient from '@/app/(protected)/traces/components/TracesClient';

interface TestRunTracesTabProps {
  testRunId: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestRunTracesTab({
  testRunId,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestRunTracesTabProps) {
  const [showEmptyHint, setShowEmptyHint] = useState(false);

  const handleUnfilteredEmpty = useCallback((empty: boolean) => {
    setShowEmptyHint(empty);
  }, []);

  return (
    <Box sx={{ position: 'relative' }}>
      {/*
       * TracesClient must stay mounted to detect the empty state via onUnfilteredEmpty.
       * When empty we collapse the wrapper to 0 height and make it invisible instead of
       * using display:none — display:none removes the element from layout and causes the
       * MUI DataGrid inside to measure a 0px width, triggering a console warning.
       */}
      <Box
        sx={
          showEmptyHint
            ? {
                position: 'absolute',
                width: '100%',
                height: 0,
                overflow: 'hidden',
                visibility: 'hidden',
                pointerEvents: 'none',
              }
            : {}
        }
      >
        <Paper
          sx={{
            width: '100%',
            borderRadius: BORDER_RADIUS.md,
            boxShadow: ELEVATION.xs,
            border: theme => `1px solid ${theme.palette.greyscale.border}`,
            overflow: 'hidden',
          }}
        >
          <TracesClient
            currentUserId={currentUserId}
            currentUserName={currentUserName}
            currentUserPicture={currentUserPicture}
            fixedTestRunId={testRunId}
            onUnfilteredEmpty={handleUnfilteredEmpty}
          />
        </Paper>
      </Box>

      {showEmptyHint && (
        <Box sx={{ mt: 3 }}>
          <EntityEmptyState
            icon={TimelineOutlinedIcon}
            title="No traces for this test run"
            description="Traces appear after test execution when endpoints are instrumented with OpenTelemetry."
          />
        </Box>
      )}
    </Box>
  );
}

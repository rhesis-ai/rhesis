'use client';

import React, { useCallback, useState } from 'react';
import { Box, Paper } from '@mui/material';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import TracesClient from '@/app/(protected)/traces/components/TracesClient';

interface TestRunTracesTabProps {
  testRunId: string;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestRunTracesTab({
  testRunId,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestRunTracesTabProps) {
  const [showEmptyHint, setShowEmptyHint] = useState(false);

  const handleUnfilteredEmpty = useCallback((empty: boolean) => {
    setShowEmptyHint(empty);
  }, []);

  return (
    <Box>
      <Paper
        sx={{
          width: '100%',
          borderRadius: BORDER_RADIUS.md,
          boxShadow: ELEVATION.xs,
          border: theme => `1px solid ${theme.palette.greyscale.border}`,
          overflow: 'hidden',
          display: showEmptyHint ? 'none' : 'block',
        }}
      >
        <TracesClient
          sessionToken={sessionToken}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
          fixedTestRunId={testRunId}
          onUnfilteredEmpty={handleUnfilteredEmpty}
        />
      </Paper>

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

'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import PlaylistAddIcon from '@mui/icons-material/PlaylistAdd';
import TestSetTestsGrid from './TestSetTestsGrid';
import TestSelectionDialog from './TestSelectionDialog';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import type { Theme } from '@mui/material/styles';

const paperSx = {
  p: 3,
  borderRadius: BORDER_RADIUS.md,
  border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  boxShadow: ELEVATION.xs,
};

interface TestSetLinkedTestsSectionProps {
  testSetId: string;
  sessionToken: string;
  testSetType?: string;
  testCount: number;
}

export default function TestSetLinkedTestsSection({
  testSetId,
  sessionToken,
  testSetType,
  testCount: initialTestCount,
}: TestSetLinkedTestsSectionProps) {
  const { show: showNotification } = useNotifications();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [totalCount, setTotalCount] = useState(initialTestCount);

  useEffect(() => {
    setTotalCount(initialTestCount);
  }, [initialTestCount]);

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  const handleAssignTests = async (tests: TestDetail[]) => {
    if (tests.length === 0) return;
    try {
      const factory = new ApiClientFactory(sessionToken);
      const testSetsClient = factory.getTestSetsClient();
      await testSetsClient.associateTestsWithTestSet(
        testSetId,
        tests.map(t => t.id as string)
      );
      showNotification(
        `${tests.length} test${tests.length === 1 ? '' : 's'} added to test set`,
        { severity: 'success', autoHideDuration: 4000 }
      );
      setDialogOpen(false);
      handleRefresh();
    } catch (error) {
      const msg = error instanceof Error ? error.message : '';
      if (msg.includes('already associated')) {
        showNotification('Some tests are already in this test set', {
          severity: 'warning',
        });
      } else {
        showNotification('Failed to add tests to test set', {
          severity: 'error',
        });
      }
    }
  };

  const isEmpty = totalCount === 0;

  const assignButton = (
    <Button
      variant="outlined"
      startIcon={<AddIcon />}
      onClick={() => setDialogOpen(true)}
    >
      Assign
    </Button>
  );

  return (
    <>
      {isEmpty ? (
        <Paper elevation={0} sx={paperSx}>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 5,
              gap: 2,
              textAlign: 'center',
            }}
          >
            <PlaylistAddIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No assigned entity yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Assign tests to this test set to group related cases together.
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setDialogOpen(true)}
            >
              Assign entity
            </Button>
          </Box>
        </Paper>
      ) : (
        <Paper elevation={0} sx={paperSx}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 3,
            }}
          >
            <Typography
              sx={{
                fontWeight: 600,
                fontSize: 20,
                lineHeight: '24px',
                color: 'primary.main',
              }}
            >
              Linked entity ({totalCount})
            </Typography>
            {assignButton}
          </Box>

          <TestSetTestsGrid
            key={refreshKey}
            testSetId={testSetId}
            sessionToken={sessionToken}
            testSetType={testSetType}
            onRefresh={handleRefresh}
            onTotalCountChange={setTotalCount}
          />
        </Paper>
      )}

      <TestSelectionDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSelect={handleAssignTests}
        sessionToken={sessionToken}
      />
    </>
  );
}

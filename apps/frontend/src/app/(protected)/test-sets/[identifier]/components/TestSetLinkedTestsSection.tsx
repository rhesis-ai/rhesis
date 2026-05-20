'use client';

import React, { useState, useCallback } from 'react';
import { Box, Button, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import PlaylistAddIcon from '@mui/icons-material/PlaylistAdd';
import TestSetTestsGrid from './TestSetTestsGrid';
import TestSelectionDialog from './TestSelectionDialog';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';

interface TestSetLinkedTestsSectionProps {
  testSetId: string;
  sessionToken: string;
  testSetType?: string;
}

export default function TestSetLinkedTestsSection({
  testSetId,
  sessionToken,
  testSetType,
}: TestSetLinkedTestsSectionProps) {
  const { show: showNotification } = useNotifications();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

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

  return (
    <>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <PlaylistAddIcon sx={{ color: 'primary.main', fontSize: 24 }} />
          <Typography
            variant="h6"
            sx={{ fontWeight: 600, color: 'primary.main' }}
          >
            Tests
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={() => setDialogOpen(true)}
          sx={{
            fontWeight: 700,
            borderWidth: 2,
            '&:hover': { borderWidth: 2 },
          }}
        >
          Assign tests
        </Button>
      </Box>

      <TestSetTestsGrid
        key={refreshKey}
        testSetId={testSetId}
        sessionToken={sessionToken}
        testSetType={testSetType}
        onRefresh={handleRefresh}
      />

      <TestSelectionDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSelect={handleAssignTests}
        sessionToken={sessionToken}
      />
    </>
  );
}

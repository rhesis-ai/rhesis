'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import PlaylistAddIcon from '@mui/icons-material/PlaylistAdd';
import { useRouter } from 'next/navigation';
import TestSetTestsGrid from './TestSetTestsGrid';
import TestSelectionDialog from './TestSelectionDialog';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import type { Theme } from '@mui/material/styles';

const POLL_INTERVAL_MS = 5000;

const paperSx = {
  p: 3,
  borderRadius: BORDER_RADIUS.md,
  border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  boxShadow: ELEVATION.xs,
};

// Grid card: no inner padding — BaseDataGrid provides the 30px insets so the
// header, toolbar, cells and footer all line up at 30px (Figma design).
const gridCardSx = {
  width: '100%',
  borderRadius: BORDER_RADIUS.md,
  border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  boxShadow: ELEVATION.xs,
  overflow: 'hidden',
};

interface TestSetLinkedTestsSectionProps {
  testSetId: string;
  sessionToken: string;
  testSetType?: string;
  testCount: number;
  isGenerating?: boolean;
}

export default function TestSetLinkedTestsSection({
  testSetId,
  sessionToken,
  testSetType,
  testCount: initialTestCount,
  isGenerating: initialIsGenerating = false,
}: TestSetLinkedTestsSectionProps) {
  const { show: showNotification } = useNotifications();
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [totalCount, setTotalCount] = useState(initialTestCount);
  const [isGenerating, setIsGenerating] = useState(initialIsGenerating);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setTotalCount(initialTestCount);
  }, [initialTestCount]);

  // Poll for generation completion when the test set is being generated
  useEffect(() => {
    if (!isGenerating) return;

    const checkStatus = async () => {
      try {
        const factory = new ApiClientFactory(sessionToken);
        const testSetsClient = factory.getTestSetsClient();
        const response = await testSetsClient.getTestSets({
          limit: 1,
          $filter: `id eq '${testSetId}'`,
        } as { limit: number; $filter: string });

        const testSet = response.data[0];
        if (!testSet) return;

        const generationStatus =
          testSet.attributes?.metadata?.generation?.status;
        if (generationStatus !== 'in_progress') {
          setIsGenerating(false);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          // Refresh the page to show completed data
          router.refresh();
        }
      } catch {
        // Silently ignore transient poll errors
      }
    };

    // Fire immediately so users don't wait a full interval for the first check.
    checkStatus();
    pollRef.current = setInterval(checkStatus, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sessionToken and testSetId are stable; router is stable
  }, [isGenerating]);

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
      {isEmpty && isGenerating ? (
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
            <CircularProgress size={36} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              Generating tests&hellip;
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Your tests are being generated in the background. This typically
              takes 2&ndash;5 minutes. The page will update automatically when
              ready.
            </Typography>
          </Box>
        </Paper>
      ) : isEmpty ? (
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
        <Paper elevation={0} sx={gridCardSx}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              px: '30px',
              pt: '30px',
              pb: '30px',
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

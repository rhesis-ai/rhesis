'use client';

import * as React from 'react';
import { Box, Button } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AddToPhotosIcon from '@mui/icons-material/AddToPhotos';
import TestSetSelectionDialog from '../../components/TestSetSelectionDialog';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { useNotifications } from '@/components/common/NotificationContext';
import TrialDrawer from '../../components/TrialDrawer';

interface TestToTestSetProps {
  sessionToken: string;
  testId: string;
  parentButton?: React.ReactNode;
}

export default function TestToTestSet({
  sessionToken,
  testId,
  parentButton,
}: TestToTestSetProps) {
  const [testSetDialogOpen, setTestSetDialogOpen] = React.useState(false);
  const [trialDrawerOpen, setTrialDrawerOpen] = React.useState(false);
  const notifications = useNotifications();

  const handleTestSetSelect = async (testSet: TestSet) => {
    if (!sessionToken) return;

    try {
      const testSetsClient = new TestSetsClient(sessionToken);
      await testSetsClient.associateTestsWithTestSet(testSet.id, [testId]);

      notifications.show(
        `Successfully associated test with test set "${testSet.name}"`,
        {
          severity: 'success',
          autoHideDuration: 6000,
        }
      );

      setTestSetDialogOpen(false);
    } catch (error) {
      // Check if the error message contains our target string
      const errorMessage = error instanceof Error ? error.message : '';
      if (
        errorMessage.includes(
          'One or more tests are already associated with this test set'
        )
      ) {
        notifications.show(
          'One or more tests are already associated with this test set',
          {
            severity: 'warning',
            autoHideDuration: 6000,
          }
        );
      } else {
        notifications.show('Failed to associate test with test set', {
          severity: 'error',
          autoHideDuration: 6000,
        });
      }
    }
  };

  const handleTrialSuccess = () => {
    setTrialDrawerOpen(false);
  };

  return (
    <>
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        {parentButton}
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddToPhotosIcon />}
          onClick={() => setTestSetDialogOpen(true)}
        >
          Assign to test set
        </Button>
        <Button
          variant="contained"
          color="primary"
          startIcon={<PlayArrowIcon />}
          onClick={() => setTrialDrawerOpen(true)}
        >
          Run Test
        </Button>
      </Box>

      <TestSetSelectionDialog
        open={testSetDialogOpen}
        onClose={() => setTestSetDialogOpen(false)}
        onSelect={handleTestSetSelect}
        sessionToken={sessionToken}
      />

      <TrialDrawer
        open={trialDrawerOpen}
        onClose={() => setTrialDrawerOpen(false)}
        sessionToken={sessionToken}
        testIds={[testId]}
        onSuccess={handleTrialSuccess}
      />
    </>
  );
}

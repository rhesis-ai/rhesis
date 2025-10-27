'use client';

import { Alert, Button, Box, CircularProgress } from '@mui/material';
import RestoreIcon from '@mui/icons-material/RestoreFromTrash';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import { useState } from 'react';
import Link from 'next/link';
import { RecycleClient } from '@/utils/api-client/recycle-client';

export interface DeletedEntityData {
  model_name: string;
  model_name_display?: string; // Formatted name like "Test Run" instead of "TestRun"
  item_name?: string; // Actual item name like "My Test Run" or "Project Alpha"
  item_id: string;
  table_name: string;
  restore_url: string;
  message: string;
}

interface DeletedEntityAlertProps {
  /**
   * Data from the 410 Gone API response
   */
  entityData: DeletedEntityData;

  /**
   * Callback when restore is successful
   */
  onRestoreSuccess?: () => void;

  /**
   * Optional session token for API calls
   */
  sessionToken?: string;

  /**
   * Optional back link URL (e.g., '/test-runs')
   */
  backUrl?: string;

  /**
   * Optional back link label
   */
  backLabel?: string;
}

/**
 * Standardized component for displaying deleted entity information
 * with restore functionality. Works across all entity types.
 */
export function DeletedEntityAlert({
  entityData,
  onRestoreSuccess,
  sessionToken,
  backUrl,
  backLabel,
}: DeletedEntityAlertProps) {
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [isRestored, setIsRestored] = useState(false);

  const handleRestore = async () => {
    if (!sessionToken) {
      setRestoreError('Authentication required to restore items');
      return;
    }

    setIsRestoring(true);
    setRestoreError(null);

    try {
      const recycleClient = new RecycleClient(sessionToken);
      await recycleClient.restoreItem(
        entityData.table_name,
        entityData.item_id
      );

      setIsRestored(true);

      // Call success callback and reload after a brief delay
      if (onRestoreSuccess) {
        onRestoreSuccess();
      } else {
        // Default behavior: reload the page after 1 second
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      }
    } catch (error) {
      console.error('Error restoring item:', error);
      setRestoreError(
        error instanceof Error ? error.message : 'Failed to restore item'
      );
    } finally {
      setIsRestoring(false);
    }
  };

  if (isRestored) {
    return (
      <Alert severity="success">
        <Box mb={3}>
          {entityData.model_name_display || entityData.model_name} has been
          restored. Reloading...
        </Box>
      </Alert>
    );
  }

  return (
    <Alert severity="warning">
      <Box mb={2}>{entityData.message}</Box>

      {restoreError && (
        <Box mt={1} color="error.main">
          Error: {restoreError}
        </Box>
      )}

      <Box display="flex" gap={2} mt={2}>
        {sessionToken && (
          <Button
            variant="contained"
            size="medium"
            startIcon={
              isRestoring ? (
                <CircularProgress size={20} color="inherit" />
              ) : (
                <RestoreIcon />
              )
            }
            onClick={handleRestore}
            disabled={isRestoring}
          >
            {isRestoring ? 'Restoring...' : 'Restore'}
          </Button>
        )}
        {backUrl && (
          <Button
            component={Link}
            href={backUrl}
            variant="outlined"
            size="medium"
            startIcon={<ArrowBackIcon />}
          >
            {backLabel || 'Back'}
          </Button>
        )}
      </Box>
    </Alert>
  );
}

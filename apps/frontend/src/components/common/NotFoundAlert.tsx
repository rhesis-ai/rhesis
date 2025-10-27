'use client';

import { Alert, Button, Box } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import SearchIcon from '@mui/icons-material/SearchOutlined';
import Link from 'next/link';
import { NotFoundEntityData } from '@/utils/entity-error-handler';

// Re-export for convenience
export type { NotFoundEntityData };

interface NotFoundAlertProps {
  /**
   * Data from the 404 Not Found API response
   */
  entityData: NotFoundEntityData;

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
 * Standardized component for displaying not found entity information.
 * Works across all entity types.
 */
export function NotFoundAlert({
  entityData,
  backUrl,
  backLabel,
}: NotFoundAlertProps) {
  const displayName = entityData.model_name_display || entityData.model_name;
  const listUrl = backUrl || entityData.list_url;
  const exploreLabel = `Explore ${displayName}s`;

  return (
    <Alert severity="warning">
      <Box mb={2}>{entityData.message}</Box>

      <Box display="flex" gap={2} flexWrap="wrap">
        <Button
          component={Link}
          href="javascript:history.back()"
          onClick={e => {
            e.preventDefault();
            window.history.back();
          }}
          variant="outlined"
          size="medium"
          startIcon={<ArrowBackIcon />}
        >
          Back
        </Button>
        <Button
          component={Link}
          href={listUrl}
          variant="contained"
          size="medium"
          startIcon={<SearchIcon />}
        >
          {exploreLabel}
        </Button>
      </Box>
    </Alert>
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import { Paper, Typography, Button, Box, Alert } from '@mui/material';
import { PageContainer } from '@toolpad/core/PageContainer';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import { usePathname } from 'next/navigation';
import { DeletedEntityAlert } from '@/components/common/DeletedEntityAlert';
import { NotFoundAlert } from '@/components/common/NotFoundAlert';
import {
  getDeletedEntityData,
  getNotFoundEntityData,
  getErrorMessage,
} from '@/utils/entity-error-handler';
import { useSession } from 'next-auth/react';

interface ErrorProps {
  error: Error & {
    digest?: string;
    status?: number;
    data?: Record<string, unknown>;
  };
  reset: () => void;
}

/**
 * Global error handler for all protected routes.
 *
 * Features:
 * - Automatically handles 404 (not found) errors with navigation UI
 * - Automatically handles 410 (deleted entity) errors with restore UI
 * - Gracefully handles all other errors with retry functionality
 * - Performance optimized with memoization
 * - Type-safe and accessible
 *
 * Works for ALL entities without manual error handling!
 */
export default function ProtectedError({ error, reset }: ErrorProps) {
  const { data: session } = useSession();
  const [isResetting, setIsResetting] = useState(false);

  // Check if this is a not found error (404)
  const notFoundEntityData = useMemo(
    () => getNotFoundEntityData(error),
    [error]
  );

  // Check if this is a deleted entity error (410)
  const deletedEntityData = useMemo(() => getDeletedEntityData(error), [error]);

  useEffect(() => {
    // Use different log levels for expected vs unexpected states
    if (notFoundEntityData) {
      console.warn('Entity not found:', {
        entity: notFoundEntityData.model_name,
        id: notFoundEntityData.item_id,
        message: notFoundEntityData.message,
      });
    } else if (deletedEntityData) {
      console.warn('Deleted entity accessed:', {
        entity: deletedEntityData.model_name,
        id: deletedEntityData.item_id,
        message: deletedEntityData.message,
      });
    } else {
      console.error('Protected route error:', {
        message: error.message,
        status: error.status,
        digest: error.digest,
        stack: error.stack,
      });

      // TODO: Send to error tracking service in production
      // if (process.env.FRONTEND_ENV === 'production') {
      //   reportErrorToService(error);
      // }
    }
  }, [error, notFoundEntityData, deletedEntityData]);

  // Get current pathname and parse segments (reactive to navigation changes)
  const pathname = usePathname();
  const pathSegments = useMemo(() => {
    return pathname.split('/').filter(Boolean);
  }, [pathname]);

  // Format entity name from URL segment (e.g., "test-runs" -> "Test Runs")
  const formatEntityName = (segment: string): string => {
    return segment
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Get page title based on error type (memoized)
  const pageTitle = useMemo(() => {
    if (notFoundEntityData) {
      const displayName =
        notFoundEntityData.model_name_display || notFoundEntityData.model_name;
      return `${displayName} not found`;
    }
    if (deletedEntityData) {
      // Use actual item name if available, otherwise use model type
      if (deletedEntityData.item_name) {
        return `${deletedEntityData.item_name} (Deleted)`;
      }
      const displayName =
        deletedEntityData.model_name_display || deletedEntityData.model_name;
      return `${displayName} Deleted`;
    }
    return 'Error';
  }, [notFoundEntityData, deletedEntityData]);

  // Determine back URL based on current path (memoized)
  const backUrl = useMemo(() => {
    if (pathSegments.length > 1) {
      return `/${pathSegments[0]}`;
    }
    return '/';
  }, [pathSegments]);

  // Get back button label (memoized)
  const backLabel = useMemo(() => {
    if (pathSegments.length > 0) {
      const entityName = formatEntityName(pathSegments[0]);
      return `Back to ${entityName}`;
    }
    return 'Back';
  }, [pathSegments]);

  // Generate breadcrumbs based on current path (memoized)
  const breadcrumbs = useMemo(() => {
    if (pathSegments.length === 0) return [];

    // Get entity name for the list page
    const entityName = formatEntityName(pathSegments[0]);

    const crumbs = [{ title: entityName, path: `/${pathSegments[0]}` }];

    // If we're on a detail page, add the current item
    if (pathSegments.length > 1) {
      const itemId = pathSegments[1];
      let itemTitle = itemId;

      if (deletedEntityData) {
        // Use actual item name if available
        if (deletedEntityData.item_name) {
          itemTitle = deletedEntityData.item_name;
        } else {
          // Fallback: show type with short ID
          const displayName =
            deletedEntityData.model_name_display ||
            deletedEntityData.model_name;
          const shortId = itemId.substring(0, 8);
          itemTitle = `${displayName} (${shortId}...)`;
        }
      }

      crumbs.push({
        title: itemTitle,
        path: typeof window !== 'undefined' ? window.location.pathname : '',
      });
    }

    return crumbs;
  }, [pathSegments, deletedEntityData]);

  // Handle reset with loading state
  const handleReset = () => {
    setIsResetting(true);
    reset();
    // Note: reset() will reload the component, so setIsResetting(false) won't be needed
  };

  return (
    <PageContainer title={pageTitle} breadcrumbs={breadcrumbs}>
      {notFoundEntityData ? (
        // Not found entity UI (404)
        <NotFoundAlert
          entityData={notFoundEntityData}
          backUrl={backUrl}
          backLabel={backLabel}
        />
      ) : deletedEntityData ? (
        // Deleted entity UI with restore functionality (410)
        <DeletedEntityAlert
          entityData={deletedEntityData}
          sessionToken={session?.session_token}
          backUrl={backUrl}
          backLabel={backLabel}
          onRestoreSuccess={() => {
            // After restore, reload the page to fetch fresh server-side data
            // Use a brief delay to let the success message show
            setTimeout(() => {
              window.location.reload();
            }, 1000);
          }}
        />
      ) : (
        // Generic error UI with retry
        <Paper role="alert" aria-live="assertive" aria-atomic="true">
          <Box p={3}>
            <Typography variant="h6" color="error" gutterBottom>
              Something went wrong
            </Typography>

            <Typography color="error" paragraph>
              {getErrorMessage(error)}
            </Typography>

            {/* Show error digest in development for debugging */}
            {process.env.FRONTEND_ENV === 'development' && error.digest && (
              <Alert severity="info">
                <Typography variant="caption" component="div">
                  <strong>Error Digest:</strong> {error.digest}
                </Typography>
                <Typography variant="caption" component="div">
                  This information helps with debugging in development.
                </Typography>
              </Alert>
            )}

            <Box display="flex" gap={2} flexWrap="wrap" mt={2}>
              <Button
                variant="contained"
                onClick={handleReset}
                disabled={isResetting}
                startIcon={<RefreshIcon />}
                aria-label="Try again to reload this page"
              >
                {isResetting ? 'Reloading...' : 'Try Again'}
              </Button>
              <Button
                component={Link}
                href={backUrl}
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                disabled={isResetting}
                aria-label={backLabel}
              >
                {backLabel}
              </Button>
            </Box>
          </Box>
        </Paper>
      )}
    </PageContainer>
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import { Paper, Typography, Button, Box, Alert } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import DetailNotFoundState from '@/components/common/DetailNotFoundState';
import EntityErrorState, {
  useEntityErrorContext,
} from '@/components/common/EntityErrorState';
import {
  getDeletedEntityData,
  getNotFoundEntityData,
  getErrorMessage,
  isForbiddenError,
  urlSegmentToResolveEntityType,
} from '@/utils/entity-error-handler';
import { publicEnv } from '@/config/runtime-config';

const SERVER_ERROR_MESSAGE =
  "This page couldn't be loaded. Try again, or go back and open it from there.";

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
 * Entity 404s render DetailNotFoundState (with cross-project resolution).
 * Deleted entities, forbidden access, and other errors have dedicated UI.
 * Server-rendered detail pages render the deleted and forbidden pages
 * themselves (`entityErrorView`): production builds strip a server error's
 * details before it gets here, so these checks only see client-side errors.
 */
export default function ProtectedError({ error, reset }: ErrorProps) {
  const [isResetting, setIsResetting] = useState(false);

  const notFoundEntityData = useMemo(
    () => getNotFoundEntityData(error),
    [error]
  );
  const isForbidden = useMemo(() => isForbiddenError(error), [error]);
  const deletedEntityData = useMemo(() => getDeletedEntityData(error), [error]);
  const { pathSegments, parsedPathEntity, backUrl, breadcrumbs, backLabel } =
    useEntityErrorContext(deletedEntityData);

  useEffect(() => {
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
    }
  }, [error, notFoundEntityData, deletedEntityData]);

  const handleReset = () => {
    setIsResetting(true);
    reset();
  };

  if (notFoundEntityData) {
    const displayName =
      notFoundEntityData.model_name_display || notFoundEntityData.model_name;

    return (
      <DetailNotFoundState
        entityLabel={displayName}
        entityId={notFoundEntityData.item_id}
        entityTableName={
          notFoundEntityData.table_name ||
          parsedPathEntity?.entityType ||
          (pathSegments[0]
            ? urlSegmentToResolveEntityType(pathSegments[0])
            : 'item')
        }
        entityData={notFoundEntityData}
        listUrl={backUrl}
        breadcrumbs={breadcrumbs}
        onBack={() => window.history.back()}
      />
    );
  }

  if (deletedEntityData) {
    return (
      <EntityErrorState kind="deleted" deletedEntity={deletedEntityData} />
    );
  }

  if (isForbidden) {
    return <EntityErrorState kind="forbidden" />;
  }

  return (
    <PageLayout title="Error" breadcrumbs={breadcrumbs}>
      <Paper role="alert" aria-live="assertive" aria-atomic="true">
        <Box p={3}>
          <Typography variant="h6" color="error" gutterBottom>
            Something went wrong
          </Typography>

          <Typography color="error" paragraph>
            {/* A server error's message is React's placeholder in production
                builds, which tells the reader nothing. */}
            {error.digest ? SERVER_ERROR_MESSAGE : getErrorMessage(error)}
          </Typography>

          {error.digest && (
            <Typography
              variant="caption"
              component="p"
              color="text.secondary"
              paragraph
            >
              Reference for support: {error.digest}
            </Typography>
          )}

          {publicEnv().environment === 'development' && error.digest && (
            <Alert severity="info">
              <Typography variant="caption" component="div">
                <strong>Error:</strong> {error.message}
              </Typography>
              <Typography variant="caption" component="div">
                Shown in development only; the reference matches the server log.
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
    </PageLayout>
  );
}
